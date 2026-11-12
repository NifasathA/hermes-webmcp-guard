"""Hermes registration using the verified current plugin API."""

from __future__ import annotations

from .config import parse_endpoints
from .schemas import CONNECT, DISCONNECT, EXECUTE, LIST_TOOLS
from .sessions import SessionManager
from .tools import BridgeTools


def register(ctx: object) -> None:
    # Current Hermes exposes plugin-relative settings one key at a time.
    # Re-wrap the endpoint value for the transport-independent parser.
    config = {"endpoints": ctx.get_config("endpoints", {}) or {}}  # type: ignore[attr-defined]
    bridge = BridgeTools(SessionManager(parse_endpoints(config)))
    for name, schema, handler in (
        ("webmcp_connect", CONNECT, bridge.connect),
        ("webmcp_list_tools", LIST_TOOLS, bridge.list_tools),
        ("webmcp_execute", EXECUTE, bridge.execute),
        ("webmcp_disconnect", DISCONNECT, bridge.disconnect),
    ):
        ctx.register_tool(name=name, toolset="webmcp", schema=schema, handler=handler)  # type: ignore[attr-defined]
    ctx.register_hook("pre_tool_call", bridge.pre_tool_call)  # type: ignore[attr-defined]
    ctx.register_middleware("tool_execution", bridge.execution_middleware)  # type: ignore[attr-defined]

    def cleanup(task_id: str = "", session_id: str = "", **kwargs: object) -> None:
        del kwargs
        bridge.manager.disconnect(task_id or session_id or "__default__")

    ctx.register_hook("on_session_end", cleanup)  # type: ignore[attr-defined]
    ctx.register_hook("on_session_reset", cleanup)  # type: ignore[attr-defined]
