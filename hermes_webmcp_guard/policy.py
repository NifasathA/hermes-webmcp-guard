"""Conservative risk classification independent of website claims."""

from __future__ import annotations

import re
from typing import Any

from .models import RawTool, Risk

_SENSITIVE = {"buy", "purchase", "pay", "payment", "checkout", "book", "booking", "reserve", "reservation", "submit", "send", "message", "email", "delete", "remove", "cancel", "close", "transfer", "withdraw", "account", "publish", "post", "confirm", "complete", "sign", "subscribe", "unsubscribe"}
_WRITE = {"create", "update", "edit", "set", "save", "add", "apply", "upload", "rename", "move", "toggle", "enable", "disable", "start"}
_READ = {"get", "list", "read", "search", "find", "lookup", "view", "inspect", "query", "filter", "sort", "preview", "check", "describe", "fetch"}
_SENSITIVE_FIELDS = {"password", "passcode", "card", "cardnumber", "cvv", "cvc", "ssn", "socialsecurity", "bankaccount", "routingnumber", "privatekey", "secret"}


def _tokens(value: str) -> set[str]:
    return {token for token in re.split(r"[^a-z0-9]+", value.lower()) if token}


def _schema_fields(schema: dict[str, Any]) -> set[str]:
    props = schema.get("properties", {})
    if not isinstance(props, dict):
        return set()
    return {re.sub(r"[^a-z0-9]", "", str(key).lower()) for key in props}


def classify(tool: RawTool) -> tuple[Risk, tuple[str, ...]]:
    """Descriptions and readOnly annotations are deliberately not trusted."""
    tokens = _tokens(tool.name)
    sensitive_names = tokens & _SENSITIVE
    sensitive_fields = _schema_fields(tool.input_schema) & _SENSITIVE_FIELDS
    if sensitive_names or sensitive_fields:
        reasons = []
        if sensitive_names:
            reasons.append("sensitive operation term: " + ", ".join(sorted(sensitive_names)))
        if sensitive_fields:
            reasons.append("sensitive input field: " + ", ".join(sorted(sensitive_fields)))
        return Risk.SENSITIVE, tuple(reasons)
    write_names = tokens & _WRITE
    if write_names:
        return Risk.WRITE, ("state-changing operation term: " + ", ".join(sorted(write_names)),)
    if tokens & _READ:
        return Risk.READ, ("recognized non-mutating operation family",)
    return Risk.SENSITIVE, ("unknown or ambiguous operation; approval required",)


def requires_approval(risk: Risk) -> bool:
    return risk is not Risk.READ

