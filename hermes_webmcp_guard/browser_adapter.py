"""Event-driven adapter for Chrome's native WebMCP CDP domain."""

from __future__ import annotations

import json
import queue
import threading
import time
import uuid
from collections.abc import Callable
from typing import Any, Protocol
from urllib.parse import urlsplit

from .config import origin_from_url
from .errors import BackendDisconnected, ExecutionUncertain, WebMCPError
from .models import BrowserIdentity, EndpointConfig, RawTool

ChangeCallback = Callable[[], None]


class BrowserAdapter(Protocol):
    @property
    def identity(self) -> BrowserIdentity: ...
    @property
    def connected(self) -> bool: ...
    def connect(self) -> None: ...
    def list_tools(self) -> list[RawTool]: ...
    def execute(self, tool: RawTool, arguments: dict[str, Any]) -> Any: ...
    def disconnect(self) -> None: ...
    def set_change_callback(self, callback: ChangeCallback) -> None: ...


class CDPWebMCPAdapter:
    """A target-scoped CDP connection; never evaluates page JavaScript."""

    def __init__(self, endpoint: EndpointConfig) -> None:
        self.endpoint = endpoint
        self._ws: Any = None
        self._connected = False
        self._send_lock = threading.Lock()
        self._state_lock = threading.RLock()
        self._next_id = 0
        self._pending: dict[int, queue.Queue[dict[str, Any]]] = {}
        self._tools: dict[tuple[str, str], RawTool] = {}
        self._invocations: dict[str, dict[str, Any]] = {}
        self._invocation_event = threading.Condition(self._state_lock)
        self._change_callback: ChangeCallback = lambda: None
        self._identity = BrowserIdentity("", "", "", "", "opaque")
        self._page_session_id: str | None = None
        self._attached_target = False

    @property
    def identity(self) -> BrowserIdentity:
        with self._state_lock:
            return self._identity

    @property
    def connected(self) -> bool:
        return self._connected

    def set_change_callback(self, callback: ChangeCallback) -> None:
        self._change_callback = callback

    def connect(self) -> None:
        try:
            import websocket
        except ImportError as exc:  # pragma: no cover
            raise BackendDisconnected("websocket-client is not installed") from exc
        headers = [f"{key}: {value}" for key, value in self.endpoint.headers.items()]
        try:
            self._ws = websocket.create_connection(
                self.endpoint.websocket_url,
                timeout=self.endpoint.connect_timeout_seconds,
                header=headers,
                enable_multithread=True,
            )
            self._connected = True
            threading.Thread(target=self._receive_loop, name="webmcp-cdp", daemon=True).start()
            tab_id = urlsplit(self.endpoint.websocket_url).path.rsplit("/", 1)[-1]
            if "/devtools/browser" in urlsplit(self.endpoint.websocket_url).path:
                targets = self._command("Target.getTargets", {}, self.endpoint.connect_timeout_seconds).get("targetInfos", [])
                candidates = [item for item in targets if item.get("type") == "page" and origin_from_url(str(item.get("url", ""))) in self.endpoint.allowed_origins]
                if self.endpoint.target_id:
                    candidates = [item for item in candidates if item.get("targetId") == self.endpoint.target_id]
                if len(candidates) != 1:
                    raise WebMCPError("browser endpoint must have exactly one allowed-origin page target (or configure target_id)")
                tab_id = str(candidates[0]["targetId"])
                attached = self._command("Target.attachToTarget", {"targetId": tab_id, "flatten": True}, self.endpoint.connect_timeout_seconds)
                self._page_session_id = str(attached["sessionId"])
                self._attached_target = True
            tree = self._command("Page.getFrameTree", {}, self.endpoint.connect_timeout_seconds, self._page_session_id)
            frame = tree["frameTree"]["frame"]
            with self._state_lock:
                self._identity = BrowserIdentity(
                    session_id=uuid.uuid4().hex,
                    tab_id=tab_id,
                    document_id=str(frame.get("loaderId") or uuid.uuid4().hex),
                    url=str(frame.get("url", "")),
                    origin=origin_from_url(str(frame.get("url", ""))),
                )
            self._command("Page.enable", {}, self.endpoint.connect_timeout_seconds, self._page_session_id)
            self._command("WebMCP.enable", {}, self.endpoint.connect_timeout_seconds, self._page_session_id)
            time.sleep(0.15)  # authoritative toolsAdded replay
        except Exception:
            self.disconnect()
            raise

    def list_tools(self) -> list[RawTool]:
        if not self._connected:
            raise BackendDisconnected("browser session is disconnected")
        with self._state_lock:
            return list(self._tools.values())

    def execute(self, tool: RawTool, arguments: dict[str, Any]) -> Any:
        if not self._connected:
            raise BackendDisconnected("browser session is disconnected")
        try:
            response = self._command(
                "WebMCP.invokeTool",
                {"frameId": tool.frame_id, "toolName": tool.name, "input": arguments},
                self.endpoint.execution_timeout_seconds,
                self._page_session_id,
            )
        except BackendDisconnected as exc:
            # Once send is attempted, a missing CDP acknowledgement cannot prove
            # that page execution did not begin.
            raise ExecutionUncertain("browser was lost while starting the website operation; outcome is uncertain and was not retried") from exc
        invocation_id = response.get("invocationId")
        if not isinstance(invocation_id, str):
            raise WebMCPError("browser returned no WebMCP invocation id")
        deadline = time.monotonic() + self.endpoint.execution_timeout_seconds
        with self._invocation_event:
            while invocation_id not in self._invocations and self._connected:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    try:
                        self._command("WebMCP.cancelInvocation", {"invocationId": invocation_id}, 2, self._page_session_id)
                    except Exception:
                        pass
                    raise ExecutionUncertain("website operation timed out; outcome is uncertain and was not retried")
                self._invocation_event.wait(remaining)
            event = self._invocations.pop(invocation_id, None)
        if event is None:
            raise BackendDisconnected("browser disconnected during website operation")
        if event.get("status") != "Completed":
            # Browser/page error text is untrusted and may echo invocation secrets.
            raise WebMCPError(f"website tool failed with status {str(event.get('status') or 'Error')[:40]}")
        output = event.get("output")
        if len(json.dumps(output, ensure_ascii=False).encode()) > self.endpoint.max_response_bytes:
            raise WebMCPError("website tool response exceeded configured size limit")
        return output

    def disconnect(self) -> None:
        was_connected = self._connected
        if self._connected and self._attached_target and self._page_session_id:
            try:
                self._command("Target.detachFromTarget", {"sessionId": self._page_session_id}, 2)
            except Exception:
                pass
        self._connected = False
        ws, self._ws = self._ws, None
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass
        with self._invocation_event:
            self._invocation_event.notify_all()
        if was_connected:
            self._change_callback()

    def _command(self, method: str, params: dict[str, Any], timeout: float, session_id: str | None = None) -> dict[str, Any]:
        if not self._connected or self._ws is None:
            raise BackendDisconnected("browser session is disconnected")
        response_queue: queue.Queue[dict[str, Any]] = queue.Queue(maxsize=1)
        with self._send_lock:
            self._next_id += 1
            command_id = self._next_id
            self._pending[command_id] = response_queue
            try:
                payload = {"id": command_id, "method": method, "params": params}
                if session_id:
                    payload["sessionId"] = session_id
                self._ws.send(json.dumps(payload))
            except Exception as exc:
                self._pending.pop(command_id, None)
                raise BackendDisconnected("failed to send command to browser") from exc
        try:
            message = response_queue.get(timeout=timeout)
        except queue.Empty:
            self._pending.pop(command_id, None)
            raise BackendDisconnected(f"browser did not answer {method} before timeout") from None
        if "error" in message:
            detail = str(message["error"].get("message", "CDP command failed"))
            raise WebMCPError(detail[:500])
        return message.get("result") or {}

    def _receive_loop(self) -> None:
        try:
            while self._connected and self._ws is not None:
                raw = self._ws.recv()
                if not raw:
                    break
                message = json.loads(raw)
                if "id" in message:
                    pending = self._pending.pop(message["id"], None)
                    if pending:
                        pending.put_nowait(message)
                elif "method" in message:
                    self._handle_event(message["method"], message.get("params") or {})
        except Exception:
            pass
        finally:
            if self._connected:
                self._connected = False
                with self._invocation_event:
                    self._invocation_event.notify_all()
                self._change_callback()

    def _handle_event(self, method: str, params: dict[str, Any]) -> None:
        changed = False
        with self._invocation_event:
            if method == "WebMCP.toolsAdded":
                for item in params.get("tools", []):
                    if not isinstance(item, dict):
                        continue
                    tool = RawTool(str(item.get("name", "")), str(item.get("description", "")), item.get("inputSchema") or {"type": "object"}, item.get("annotations") or {}, str(item.get("frameId", "")))
                    self._tools[(tool.frame_id, tool.name)] = tool
                    changed = True
            elif method == "WebMCP.toolsRemoved":
                for item in params.get("tools", []):
                    if isinstance(item, dict):
                        changed |= self._tools.pop((str(item.get("frameId", "")), str(item.get("name", ""))), None) is not None
            elif method == "WebMCP.toolResponded":
                invocation_id = params.get("invocationId")
                if isinstance(invocation_id, str):
                    self._invocations[invocation_id] = params  # retain event-before-response races
                    self._invocation_event.notify_all()
            elif method == "Page.frameNavigated":
                frame = params.get("frame") or {}
                if not frame.get("parentId"):
                    old = self._identity
                    self._tools.clear()
                    self._identity = BrowserIdentity(old.session_id, old.tab_id, str(frame.get("loaderId") or uuid.uuid4().hex), str(frame.get("url", "")), origin_from_url(str(frame.get("url", ""))))
                    changed = True
        if changed:
            self._change_callback()
