from __future__ import annotations

import json
import queue

from hermes_webmcp_guard.browser_adapter import CDPWebMCPAdapter
from hermes_webmcp_guard.models import EndpointConfig


class FakeWebSocket:
    def __init__(self):
        self.messages = queue.Queue()
        self.closed = False

    def send(self, raw):
        call = json.loads(raw)
        method = call["method"]
        if method == "Page.getFrameTree":
            result = {"frameTree": {"frame": {"id": "f", "loaderId": "doc", "url": "https://demo.example/app"}}}
        elif method == "WebMCP.enable":
            self.messages.put(json.dumps({"method": "WebMCP.toolsAdded", "params": {"tools": [{"name": "search_location", "description": "search", "inputSchema": {"type": "object"}, "frameId": "f"}]}}))
            result = {}
        elif method == "WebMCP.invokeTool":
            # Deliberately deliver completion before the command response.
            self.messages.put(json.dumps({"method": "WebMCP.toolResponded", "params": {"invocationId": "i-1", "status": "Completed", "output": {"ok": True}}}))
            result = {"invocationId": "i-1"}
        else:
            result = {}
        self.messages.put(json.dumps({"id": call["id"], "result": result}))

    def recv(self):
        if self.closed:
            return ""
        return self.messages.get(timeout=2)

    def close(self):
        self.closed = True
        self.messages.put("")


def test_native_cdp_discovery_and_early_completion(monkeypatch):
    socket = FakeWebSocket()
    monkeypatch.setattr("websocket.create_connection", lambda *args, **kwargs: socket)
    endpoint = EndpointConfig("native", "wss://browser.example/devtools/page/tab", ("https://demo.example",))
    adapter = CDPWebMCPAdapter(endpoint)
    adapter.connect()
    tool = adapter.list_tools()[0]
    assert tool.name == "search_location"
    assert adapter.execute(tool, {}) == {"ok": True}
    adapter.disconnect()

