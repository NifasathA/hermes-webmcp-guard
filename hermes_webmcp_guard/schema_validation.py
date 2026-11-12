"""Strict validation for untrusted website schemas and invocation input."""

from __future__ import annotations

from typing import Any

from jsonschema import Draft202012Validator, SchemaError, ValidationError

from .errors import ArgumentsRejected, SchemaRejected

_MAX_SCHEMA_DEPTH = 20
_MAX_SCHEMA_NODES = 2_000
_MAX_ARGUMENT_BYTES = 65_536


def _measure(value: Any, depth: int = 0) -> int:
    if depth > _MAX_SCHEMA_DEPTH:
        raise SchemaRejected("website tool schema exceeds maximum nesting depth")
    if isinstance(value, dict):
        return 1 + sum(_measure(k, depth + 1) + _measure(v, depth + 1) for k, v in value.items())
    if isinstance(value, list):
        return 1 + sum(_measure(v, depth + 1) for v in value)
    return 1


def validate_tool_schema(schema: Any) -> dict[str, Any]:
    if not isinstance(schema, dict):
        raise SchemaRejected("website tool inputSchema must be an object")
    if _measure(schema) > _MAX_SCHEMA_NODES:
        raise SchemaRejected("website tool schema is too large")
    if schema.get("type", "object") != "object":
        raise SchemaRejected("website tool inputSchema root must be type object")
    _reject_remote_refs(schema)
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise SchemaRejected(f"website tool has an invalid JSON schema: {exc.message}") from None
    return schema


def validate_arguments(schema: dict[str, Any], arguments: Any) -> dict[str, Any]:
    if not isinstance(arguments, dict):
        raise ArgumentsRejected("arguments must be a JSON object")
    import json
    if len(json.dumps(arguments, ensure_ascii=False).encode()) > _MAX_ARGUMENT_BYTES:
        raise ArgumentsRejected("arguments exceed the 65536-byte limit")
    if _measure(arguments) > _MAX_SCHEMA_NODES:
        raise ArgumentsRejected("arguments contain too many nested values")
    try:
        Draft202012Validator(schema).validate(arguments)
    except ValidationError as exc:
        path = "/".join(str(item) for item in exc.absolute_path) or "<root>"
        raise ArgumentsRejected(f"arguments failed {exc.validator!r} validation at {path}") from None
    return arguments


def _reject_remote_refs(value: Any) -> None:
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str) and not ref.startswith("#"):
            raise SchemaRejected("remote JSON Schema references are forbidden")
        for item in value.values():
            _reject_remote_refs(item)
    elif isinstance(value, list):
        for item in value:
            _reject_remote_refs(item)
