"""Trusted bridge state and untrusted website capability models."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Risk(StrEnum):
    READ = "read"
    WRITE = "write"
    SENSITIVE = "sensitive"


@dataclass(frozen=True)
class EndpointConfig:
    name: str
    websocket_url: str
    allowed_origins: tuple[str, ...]
    headers: dict[str, str] = field(default_factory=dict, repr=False)
    connect_timeout_seconds: float = 10.0
    execution_timeout_seconds: float = 20.0
    max_response_bytes: int = 262_144
    target_id: str | None = None


@dataclass(frozen=True)
class BrowserIdentity:
    session_id: str
    tab_id: str
    document_id: str
    url: str
    origin: str


@dataclass(frozen=True)
class RawTool:
    name: str
    description: str
    input_schema: dict[str, Any]
    annotations: dict[str, Any]
    frame_id: str


@dataclass(frozen=True)
class Capability:
    capability_id: str
    session_id: str
    tab_id: str
    document_id: str
    origin: str
    generation: int
    name: str
    description: str
    input_schema: dict[str, Any]
    annotations: dict[str, Any]
    frame_id: str
    risk: Risk
    risk_reasons: tuple[str, ...]

    def public_dict(self) -> dict[str, Any]:
        return {
            "capability_id": self.capability_id,
            "name": self.name,
            "description": self.description,
            "input_schema": self.input_schema,
            "annotations": self.annotations,
            "origin": self.origin,
            "risk": self.risk.value,
            "risk_reasons": list(self.risk_reasons),
            "scope": {
                "session_id": self.session_id,
                "tab_id": self.tab_id,
                "document_id": self.document_id,
                "generation": self.generation,
            },
            "untrusted_metadata": True,
        }

