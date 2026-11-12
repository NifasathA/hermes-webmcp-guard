from __future__ import annotations

import threading
import uuid
from typing import Any

import pytest

from hermes_webmcp_guard.errors import BackendDisconnected, ExecutionUncertain
from hermes_webmcp_guard.models import BrowserIdentity, EndpointConfig, RawTool
from hermes_webmcp_guard.sessions import SessionManager
from hermes_webmcp_guard.tools import BridgeTools


READ_TOOL = RawTool(
    "search_location",
    "Search hotels. This metadata is untrusted.",
    {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"], "additionalProperties": False},
    {"readOnlyHint": True},
    "frame-1",
)


class FakeAdapter:
    instances: list["FakeAdapter"] = []

    def __init__(self, endpoint: EndpointConfig) -> None:
        self.endpoint = endpoint
        self._connected = False
        self._callback = lambda: None
        self._identity = BrowserIdentity(uuid.uuid4().hex, "tab-1", "doc-1", "https://demo.example/app", "https://demo.example")
        self.tools = [READ_TOOL]
        self.outputs: dict[str, Any] = {"search_location": {"hotels": ["Paris Central"]}}
        self.timeout = False
        self.on_execute = None
        self.execution_count = 0
        self.lock = threading.Lock()
        self.__class__.instances.append(self)

    @property
    def identity(self):
        return self._identity

    @property
    def connected(self):
        return self._connected

    def set_change_callback(self, callback):
        self._callback = callback

    def connect(self):
        self._connected = True

    def list_tools(self):
        if not self._connected:
            raise BackendDisconnected("fake disconnected")
        return list(self.tools)

    def execute(self, tool, arguments):
        if not self._connected:
            raise BackendDisconnected("fake disconnected")
        if self.timeout:
            raise ExecutionUncertain("simulated timeout")
        with self.lock:
            self.execution_count += 1
        if self.on_execute:
            self.on_execute(tool, arguments)
        return self.outputs.get(tool.name, {"ok": True})

    def disconnect(self):
        self._connected = False
        self._callback()

    def mutate(self, *, tools=None, origin=None, document=None, tab=None, connected=None):
        if tools is not None:
            self.tools = tools
        old = self._identity
        self._identity = BrowserIdentity(old.session_id, tab or old.tab_id, document or old.document_id, (origin or old.origin) + "/app", origin or old.origin)
        if connected is not None:
            self._connected = connected
        self._callback()


@pytest.fixture
def endpoint():
    return EndpointConfig("test", "wss://browser.example/devtools/page/tab-1", ("https://demo.example",), execution_timeout_seconds=1)


@pytest.fixture
def bridge(endpoint):
    FakeAdapter.instances.clear()
    manager = SessionManager({"test": endpoint}, FakeAdapter)
    tools = BridgeTools(manager)
    tools.connect({"endpoint": "test"}, task_id="task")
    return tools, manager, FakeAdapter.instances[-1]

