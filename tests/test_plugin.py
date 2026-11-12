from __future__ import annotations

from hermes_webmcp_guard.plugin import register


class Context:
    def __init__(self):
        self.tools = {}
        self.hooks = {}
        self.middleware = {}

    def get_config(self, key, default=None):
        if key == "endpoints":
            return {}
        return default

    def register_tool(self, **kwargs):
        self.tools[kwargs["name"]] = kwargs

    def register_hook(self, name, callback):
        self.hooks[name] = callback

    def register_middleware(self, name, callback):
        self.middleware[name] = callback


def test_verified_hermes_registration_surface():
    ctx = Context()
    register(ctx)
    assert set(ctx.tools) == {"webmcp_connect", "webmcp_list_tools", "webmcp_execute", "webmcp_disconnect"}
    assert set(ctx.hooks) == {"pre_tool_call", "on_session_end", "on_session_reset"}
    assert set(ctx.middleware) == {"tool_execution"}
    assert all(tool["toolset"] == "webmcp" for tool in ctx.tools.values())
