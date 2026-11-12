from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from hermes_webmcp_guard.models import RawTool


def parsed(value):
    return json.loads(value)


def cap(tools):
    return parsed(tools.list_tools({}, task_id="task"))["capabilities"][0]


def test_changing_capability_set_invalidates_previous_ids(bridge):
    tools, _, adapter = bridge
    old = cap(tools)
    adapter.mutate(tools=[RawTool("filter_search_results", "", {"type": "object"}, {}, "f")])
    parsed(tools.list_tools({}, task_id="task"))
    result = parsed(tools.execute({"capability_id": old["capability_id"], "arguments": {"query": "Paris"}}, task_id="task", tool_call_id="x"))
    assert result["error"] == "CAPABILITY_STALE"


def test_origin_change_is_denied_and_old_capability_is_stale(bridge):
    tools, _, adapter = bridge
    old = cap(tools)
    adapter.mutate(origin="https://evil.example", document="doc-2")
    result = parsed(tools.execute({"capability_id": old["capability_id"], "arguments": {"query": "Paris"}}, task_id="task", tool_call_id="x"))
    assert result["error"] == "ORIGIN_DENIED"


def test_tab_change_invalidates_previous_capability(bridge):
    tools, _, adapter = bridge
    old = cap(tools)
    adapter.mutate(tab="tab-2", document="doc-2")
    result = parsed(tools.execute({"capability_id": old["capability_id"], "arguments": {"query": "Paris"}}, task_id="task", tool_call_id="x"))
    assert result["error"] == "CAPABILITY_STALE"


def test_session_expiration_and_backend_disconnect(bridge):
    tools, _, adapter = bridge
    old = cap(tools)
    adapter.mutate(connected=False)
    listed = parsed(tools.list_tools({}, task_id="task"))
    assert listed["error"] == "BACKEND_DISCONNECTED"
    attempted = parsed(tools.execute({"capability_id": old["capability_id"], "arguments": {"query": "Paris"}}, task_id="task", tool_call_id="x"))
    assert attempted["error"] in {"CAPABILITY_STALE", "BACKEND_DISCONNECTED"}


def test_disconnect_revokes_capabilities(bridge):
    tools, _, _ = bridge
    old = cap(tools)
    assert parsed(tools.disconnect({}, task_id="task"))["capabilities_revoked"]
    result = parsed(tools.execute({"capability_id": old["capability_id"], "arguments": {"query": "Paris"}}, task_id="task", tool_call_id="x"))
    assert result["error"] == "BACKEND_DISCONNECTED"


def test_timeout_has_uncertain_outcome_and_no_retry(bridge):
    tools, _, adapter = bridge
    current = cap(tools)
    adapter.timeout = True
    result = parsed(tools.execute({"capability_id": current["capability_id"], "arguments": {"query": "Paris"}}, task_id="task", tool_call_id="x"))
    assert result["outcome_uncertain"] is True
    assert result["retried"] is False


def test_concurrent_discovery_and_invocation_are_serialized(bridge):
    tools, _, adapter = bridge
    current = cap(tools)
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(tools.list_tools, {}, task_id="task") for _ in range(4)]
        futures += [pool.submit(tools.execute, {"capability_id": current["capability_id"], "arguments": {"query": "Paris"}}, task_id="task", tool_call_id=f"r{i}") for i in range(4)]
    results = [parsed(f.result()) for f in futures]
    assert all(item["ok"] for item in results)
    assert adapter.execution_count == 4

