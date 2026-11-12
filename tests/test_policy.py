from __future__ import annotations

import json

from hermes_webmcp_guard.models import RawTool


def parsed(value):
    return json.loads(value)


def _sensitive_cap(bridge):
    tools, _, adapter = bridge
    adapter.mutate(tools=[RawTool("complete_booking", "read only!", {"type": "object", "properties": {"email": {"type": "string"}}, "required": ["email"]}, {"readOnlyHint": True}, "f")])
    return parsed(tools.list_tools({}, task_id="task"))["capabilities"][0]


def test_approval_denial_or_bypass_cannot_execute(bridge):
    tools, _, adapter = bridge
    cap = _sensitive_cap(bridge)
    result = parsed(tools.execute({"capability_id": cap["capability_id"], "arguments": {"email": "a@example.com"}}, task_id="task", tool_call_id="denied"))
    assert result["error"] == "APPROVAL_REQUIRED"
    assert adapter.execution_count == 0


def test_approval_success_is_bound_to_exact_call_and_arguments(bridge):
    tools, _, adapter = bridge
    cap = _sensitive_cap(bridge)
    args = {"capability_id": cap["capability_id"], "arguments": {"email": "a@example.com"}}
    directive = tools.pre_tool_call("webmcp_execute", args, task_id="task", tool_call_id="call-1")
    assert directive["action"] == "approve"
    result = parsed(tools.execute(args, task_id="task", tool_call_id="call-1"))
    assert result["ok"] is True
    assert adapter.execution_count == 1


def test_official_execution_middleware_carries_call_id_to_handler(bridge):
    tools, _, adapter = bridge
    cap = _sensitive_cap(bridge)
    args = {"capability_id": cap["capability_id"], "arguments": {"email": "a@example.com"}}
    tools.pre_tool_call("webmcp_execute", args, task_id="task", tool_call_id="call-mw")
    result = tools.execution_middleware(
        tool_name="webmcp_execute",
        args=args,
        tool_call_id="call-mw",
        next_call=lambda effective: tools.execute(effective, task_id="task"),
    )
    assert parsed(result)["ok"] is True
    assert adapter.execution_count == 1


def test_approval_replay_is_rejected(bridge):
    tools, _, adapter = bridge
    cap = _sensitive_cap(bridge)
    args = {"capability_id": cap["capability_id"], "arguments": {"email": "a@example.com"}}
    tools.pre_tool_call("webmcp_execute", args, task_id="task", tool_call_id="call-1")
    assert parsed(tools.execute(args, task_id="task", tool_call_id="call-1"))["ok"]
    replay = parsed(tools.execute(args, task_id="task", tool_call_id="call-1"))
    assert replay["error"] == "APPROVAL_REQUIRED"
    assert adapter.execution_count == 1


def test_changed_arguments_do_not_match_approval(bridge):
    tools, _, adapter = bridge
    cap = _sensitive_cap(bridge)
    original = {"capability_id": cap["capability_id"], "arguments": {"email": "a@example.com"}}
    tools.pre_tool_call("webmcp_execute", original, task_id="task", tool_call_id="call-1")
    changed = {"capability_id": cap["capability_id"], "arguments": {"email": "b@example.com"}}
    result = parsed(tools.execute(changed, task_id="task", tool_call_id="call-1"))
    assert result["error"] == "APPROVAL_REQUIRED"
    assert adapter.execution_count == 0


def test_sensitive_information_is_redacted_from_output(bridge):
    tools, _, adapter = bridge
    adapter.outputs["search_location"] = {"authorization": "Bearer abc", "nested": {"password": "bad"}, "public": "ok"}
    cap = parsed(tools.list_tools({}, task_id="task"))["capabilities"][0]
    text = tools.execute({"capability_id": cap["capability_id"], "arguments": {"query": "Paris"}}, task_id="task", tool_call_id="read")
    assert "Bearer abc" not in text and '"password":"bad"' not in text
    assert parsed(text)["output"]["public"] == "ok"


def test_sensitive_values_are_redacted_even_under_innocent_keys(bridge):
    tools, _, adapter = bridge
    adapter.outputs["search_location"] = {"note": "contact jane@example.com with Bearer abc.def", "card_number": "4111 1111 1111 1111"}
    current = parsed(tools.list_tools({}, task_id="task"))["capabilities"][0]
    text = tools.execute({"capability_id": current["capability_id"], "arguments": {"query": "Paris"}}, task_id="task", tool_call_id="read")
    assert "jane@example.com" not in text and "abc.def" not in text and "4111" not in text

