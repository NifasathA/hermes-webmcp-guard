"""Configuration parsing and endpoint security validation."""

from __future__ import annotations

import ipaddress
from typing import Any
from urllib.parse import urlsplit

from .errors import ConfigurationError, ConnectionRejected
from .models import EndpointConfig


_METADATA_IPS = {"169.254.169.254", "100.100.100.200"}


def _is_loopback(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def validate_endpoint_url(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.username or parsed.password:
        raise ConnectionRejected("CDP endpoint URLs must not contain credentials")
    if parsed.scheme not in {"ws", "wss"} or not parsed.hostname:
        raise ConnectionRejected("CDP endpoint must be an explicit ws:// or wss:// URL")
    host = parsed.hostname.lower()
    if host in _METADATA_IPS:
        raise ConnectionRejected("cloud metadata endpoints are forbidden")
    if parsed.scheme == "ws" and not _is_loopback(host):
        raise ConnectionRejected("remote CDP endpoints must use TLS (wss://)")
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return
    if (ip.is_private or ip.is_link_local or ip.is_reserved) and not ip.is_loopback:
        raise ConnectionRejected("private and link-local CDP endpoints are forbidden")


def parse_endpoints(config: dict[str, Any] | None) -> dict[str, EndpointConfig]:
    raw = (config or {}).get("endpoints", {})
    if not isinstance(raw, dict):
        raise ConfigurationError("endpoints must be a mapping")
    endpoints: dict[str, EndpointConfig] = {}
    for name, item in raw.items():
        if not isinstance(name, str) or not isinstance(item, dict):
            raise ConfigurationError("each endpoint must be a named mapping")
        url = item.get("websocket_url")
        origins = item.get("allowed_origins")
        if not isinstance(url, str) or not isinstance(origins, list) or not origins:
            raise ConfigurationError(f"endpoint {name!r} needs websocket_url and allowed_origins")
        validate_endpoint_url(url)
        clean_origins = tuple(_canonical_origin(value) for value in origins)
        if "headers" in item or "headers_env" in item:
            raise ConfigurationError(
                f"endpoint {name!r} must not contain credentials; use an authenticated local CDP proxy"
            )
        endpoints[name] = EndpointConfig(
            name=name,
            websocket_url=url,
            allowed_origins=clean_origins,
            connect_timeout_seconds=_bounded_float(item.get("connect_timeout_seconds", 10), 1, 30),
            execution_timeout_seconds=_bounded_float(item.get("execution_timeout_seconds", 20), 1, 120),
            max_response_bytes=int(_bounded_float(item.get("max_response_bytes", 262_144), 1_024, 1_048_576)),
            target_id=str(item["target_id"]) if item.get("target_id") else None,
        )
    return endpoints


def _bounded_float(value: Any, low: float, high: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not low <= float(value) <= high:
        raise ConfigurationError(f"numeric configuration value must be between {low} and {high}")
    return float(value)


def _canonical_origin(value: Any) -> str:
    if not isinstance(value, str):
        raise ConfigurationError("allowed origins must be strings")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.path not in {"", "/"}:
        raise ConfigurationError(f"invalid origin allowlist entry: {value!r}")
    default = (parsed.scheme == "https" and parsed.port in {None, 443}) or (parsed.scheme == "http" and parsed.port in {None, 80})
    port = "" if default else f":{parsed.port}"
    return f"{parsed.scheme}://{parsed.hostname.lower()}{port}"


def origin_from_url(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return "opaque"
    default = (parsed.scheme == "https" and parsed.port in {None, 443}) or (parsed.scheme == "http" and parsed.port in {None, 80})
    port = "" if default else f":{parsed.port}"
    return f"{parsed.scheme}://{parsed.hostname.lower()}{port}"
