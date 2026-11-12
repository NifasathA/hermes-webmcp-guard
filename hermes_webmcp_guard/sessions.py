"""Capability lifecycle and per-Hermes-session isolation."""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass, field
from typing import Any

from .browser_adapter import BrowserAdapter, CDPWebMCPAdapter
from .errors import BackendDisconnected, CapabilityStale, ConfigurationError, OriginDenied, SchemaRejected
from .models import Capability, EndpointConfig, RawTool
from .policy import classify
from .schema_validation import validate_arguments, validate_tool_schema


def _capability_id(identity: Any, generation: int, tool: RawTool) -> str:
    payload = json.dumps({
        "session": identity.session_id,
        "tab": identity.tab_id,
        "document": identity.document_id,
        "origin": identity.origin,
        "generation": generation,
        "frame": tool.frame_id,
        "name": tool.name,
        "schema": tool.input_schema,
    }, sort_keys=True, separators=(",", ":"))
    return "wcap_" + hashlib.sha256(payload.encode()).hexdigest()[:32]


@dataclass
class BridgeSession:
    endpoint: EndpointConfig
    adapter: BrowserAdapter
    generation: int = 0
    capabilities: dict[str, Capability] = field(default_factory=dict)
    raw_tools: dict[str, RawTool] = field(default_factory=dict)
    invalid_schemas: list[dict[str, str]] = field(default_factory=list)
    lock: threading.RLock = field(default_factory=threading.RLock)
    dirty: threading.Event = field(default_factory=threading.Event)

    def mark_dirty(self) -> None:
        self.dirty.set()  # non-blocking: called on the CDP receiver thread

    def invalidate_if_dirty(self) -> None:
        if self.dirty.is_set():
            self.generation += 1
            self.capabilities.clear()
            self.raw_tools.clear()
            self.dirty.clear()

    def assert_origin(self) -> None:
        origin = self.adapter.identity.origin
        if origin not in self.endpoint.allowed_origins:
            raise OriginDenied(f"active page origin {origin!r} is not approved for endpoint {self.endpoint.name!r}")

    def discover(self) -> list[Capability]:
        with self.lock:
            self.invalidate_if_dirty()
            if not self.adapter.connected:
                raise BackendDisconnected("browser session is disconnected")
            self.assert_origin()
            tools = self.adapter.list_tools()
            current_fingerprint = {(t.frame_id, t.name, json.dumps(t.input_schema, sort_keys=True), t.description) for t in tools}
            old_fingerprint = {(t.frame_id, t.name, json.dumps(t.input_schema, sort_keys=True), t.description) for t in self.raw_tools.values()}
            if self.capabilities and current_fingerprint != old_fingerprint:
                self.generation += 1
                self.capabilities.clear()
                self.raw_tools.clear()
            self.invalid_schemas = []
            discovered: dict[str, Capability] = {}
            raw: dict[str, RawTool] = {}
            for tool in tools:
                try:
                    schema = validate_tool_schema(tool.input_schema)
                except SchemaRejected as exc:
                    self.invalid_schemas.append({"name": tool.name, "error": str(exc)})
                    continue
                normalized = RawTool(tool.name, tool.description, schema, tool.annotations, tool.frame_id)
                risk, reasons = classify(normalized)
                cap_id = _capability_id(self.adapter.identity, self.generation, normalized)
                identity = self.adapter.identity
                capability = Capability(cap_id, identity.session_id, identity.tab_id, identity.document_id, identity.origin, self.generation, normalized.name, normalized.description, schema, normalized.annotations, normalized.frame_id, risk, reasons)
                discovered[cap_id] = capability
                raw[cap_id] = normalized
            self.capabilities = discovered
            self.raw_tools = raw
            return list(discovered.values())

    def resolve(self, capability_id: str, arguments: Any) -> tuple[Capability, RawTool, dict[str, Any]]:
        with self.lock:
            self.invalidate_if_dirty()
            self.assert_origin()
            capability = self.capabilities.get(capability_id)
            raw = self.raw_tools.get(capability_id)
            if capability is None or raw is None:
                raise CapabilityStale("capability ID is stale, unknown, or belongs to another browser context; run webmcp_list_tools again")
            identity = self.adapter.identity
            if (capability.session_id, capability.tab_id, capability.document_id, capability.origin, capability.generation) != (identity.session_id, identity.tab_id, identity.document_id, identity.origin, self.generation):
                raise CapabilityStale("capability scope no longer matches the active browser document")
            return capability, raw, validate_arguments(capability.input_schema, arguments)


class SessionManager:
    def __init__(self, endpoints: dict[str, EndpointConfig], adapter_factory: Any = CDPWebMCPAdapter) -> None:
        self.endpoints = endpoints
        self.adapter_factory = adapter_factory
        self._sessions: dict[str, BridgeSession] = {}
        self._lock = threading.RLock()

    def connect(self, owner: str, endpoint_name: str) -> BridgeSession:
        endpoint = self.endpoints.get(endpoint_name)
        if endpoint is None:
            raise ConfigurationError(f"unknown configured endpoint {endpoint_name!r}")
        self.disconnect(owner)
        adapter = self.adapter_factory(endpoint)
        session = BridgeSession(endpoint, adapter)
        adapter.set_change_callback(session.mark_dirty)
        adapter.connect()
        try:
            session.assert_origin()
            session.discover()
        except Exception:
            adapter.disconnect()
            raise
        with self._lock:
            self._sessions[owner] = session
        return session

    def get(self, owner: str) -> BridgeSession:
        with self._lock:
            session = self._sessions.get(owner)
        if session is None:
            raise BackendDisconnected("no WebMCP browser is connected for this Hermes session")
        return session

    def disconnect(self, owner: str) -> bool:
        with self._lock:
            session = self._sessions.pop(owner, None)
        if session is None:
            return False
        with session.lock:
            session.generation += 1
            session.capabilities.clear()
            session.raw_tools.clear()
            session.adapter.disconnect()
        return True

    def disconnect_all(self) -> None:
        with self._lock:
            owners = list(self._sessions)
        for owner in owners:
            self.disconnect(owner)
