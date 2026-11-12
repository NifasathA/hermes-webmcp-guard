# Research: Hermes WebMCP Guard

Research date: 2026-11-11. Sources below are primary project documentation or source repositories as they existed on that date. Hermes and WebMCP are moving quickly, so the plugin should declare and test a minimum Hermes version rather than assuming older releases have the same hook and browser seams.

## Executive conclusion

Hermes already has nearly all of the host-side primitives this plugin needs: native Python plugins register stable tools with `ctx.register_tool`, `pre_tool_call` can block or escalate a call to Hermes's human-approval gate, and a trusted plugin can capture a task's existing CDP supervisor connection. Chrome DevTools MCP already implements WebMCP discovery and execution. Therefore, the bridge should not claim to invent WebMCP transport. Its distinct contribution is a stable, permission-aware facade with capability IDs bound to a browser session, page/document, origin, generation, and exact arguments.

The smallest defensible vertical slice is:

1. register four fixed Hermes tools (`webmcp_connect`, `webmcp_list_tools`, `webmcp_execute`, `webmcp_disconnect`);
2. attach only to an explicitly configured CDP endpoint or an already-running Hermes task supervisor;
3. use a standards-compatible WebMCP backend (prefer Chrome DevTools MCP's WebMCP tools; permit a direct CDP adapter for WebMCP-enabled endpoints where needed);
4. normalize discovery into plugin-owned, opaque capability IDs;
5. validate the current target/document/origin and JSON Schema immediately before execution;
6. return a `pre_tool_call` `approve` directive for write, sensitive, unknown, or ambiguous operations and fail closed if that directive is unavailable.

## 1. Hermes plugin registration and hooks

Hermes native plugins are directories containing `plugin.yaml` plus `__init__.py` with a `register(ctx)` function. The documented registration shape is `ctx.register_tool(name=..., toolset=..., schema=..., handler=...)`; registration happens once at startup and the resulting tools are visible to the model. The manifest's `provides_tools` and `provides_hooks` fields describe what will be registered. Project-local plugins are deliberately disabled unless `HERMES_ENABLE_PROJECT_PLUGINS=true` is set. Sources: [Hermes plugin guide](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/plugins/index.md), [plugins user guide](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/plugins.md).

The verified tool registration pattern on current `main` is:

```python
def register(ctx):
    ctx.register_tool(
        name="webmcp_execute",
        toolset="webmcp",
        schema=WEBMCP_EXECUTE,
        handler=execute,
    )
```

Hermes documents native plugin behavior as an additive compatibility contract, not a single global plugin API version. A marketplace submission should still set a `requires_hermes` floor corresponding to the release where approval directives and public CDP capture are present. Source: [native plugin compatibility contract](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/plugins/index.md#native-plugin-compatibility-contract).

### Approval enforcement

`pre_tool_call` fires immediately before built-in and plugin tools. Its callback receives `tool_name`, `args`, and `task_id` (plus additive keyword fields). Current Hermes accepts:

```python
return {"action": "block", "message": "..."}
return {"action": "approve", "message": "...", "rule_key": "..."}
```

`block` takes precedence over `approve`; denial, timeout, or approval-gate failure fails closed. A callback exception or timeout also blocks rather than silently proceeding. This is the supported enforcement point for `webmcp_execute`. Source: [Hermes hooks: `pre_tool_call`](https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks#pre_tool_call).

Important limitation: Hermes's approval system may offer choices broader than “once” on some surfaces. The bridge must therefore treat the Hermes prompt only as authorization for the single pending invocation. It must bind an internal one-use approval record to the exact session, target/document, origin, capability digest, canonical validated arguments, and invocation nonce; it must consume that record once. A session/always answer from the generic gate must not become a blanket website permission.

Hermes currently sends `tool_call_id` to hooks and official `tool_execution` middleware but registry handlers receive task/session IDs only. The implementation therefore uses the documented middleware wrapper to carry the ID across the post-approval execution boundary; the handler fails closed if that context is absent. Source: [Hermes middleware contract](https://hermes-agent.nousresearch.com/docs/developer-guide/middleware#tool-calls).

`post_approval_response` observes choices but cannot itself veto or answer approvals. It can support audit/nonce bookkeeping, while final execution checks still belong inside `webmcp_execute`. Source: [approval hook documentation](https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks#post_approval_response).

## 2. Hermes browser sessions exposed to plugins

Hermes browser automation is task-scoped. Its CDP supervisor holds one persistent WebSocket per browser task, tracks page/frame state, and is stopped on teardown or re-bound when the endpoint changes. Source: [Hermes Browser CDP Supervisor](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/browser-supervisor.md).

Current Hermes exposes a public trusted-plugin seam:

```python
from tools.browser_supervisor import SUPERVISOR_REGISTRY

cdp = SUPERVISOR_REGISTRY.capture(task_id)
reply = cdp.call(method, params, session_id=cdp.page_session_id, timeout=5)
```

The capture is pinned: it becomes invalid if the supervisor reconnects, stops, or is replaced; it never follows a new connection. This is useful lifecycle evidence. It does **not** enforce origin, consent, or target ownership, and Hermes explicitly requires plugins to provide those controls. Source: [trusted plugin CDP access](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/developer-guide/browser-supervisor.md#trusted-plugin-cdp-access).

Hermes also permits attaching browser tools to an explicit `browser.cdp_url` or `/browser connect` endpoint. The standard local/cloud browser launched for `browser_exec` and externally attached CDP sessions have different availability constraints; an implementation must not represent a newly launched external browser as the user's existing Hermes browser. Source: [Hermes browser automation](https://hermes-agent.nousresearch.com/docs/user-guide/features/browser).

Implementation implication: support two explicit connection modes and report which one is active:

- `hermes_supervisor`: capture the calling task's already-running supervisor; never start or refocus it.
- `configured_endpoint`: connect to a configured endpoint after SSRF/TLS checks and identify the actual browser/target selected.

Do not silently fall back between the two.

## 3. Existing Hermes MCP and Chrome DevTools MCP capability

Hermes already supports configured MCP servers and dynamically registers their tools under an `mcp__<server>__...` prefix. It can run Chrome DevTools MCP as an external MCP server. Sources: [Hermes MCP guide](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/mcp.md), [using MCP with Hermes](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/guides/use-mcp-with-hermes.md).

Chrome DevTools MCP added experimental WebMCP support in release 0.22.0 and currently exposes `list_webmcp_tools(pageId)` and `execute_webmcp_tool(pageId, toolName, input)` when `--categoryExperimentalWebmcp` is enabled. The category is off by default. Sources: [Chrome DevTools MCP tool reference](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/main/docs/tool-reference.md#webmcp), [Chrome DevTools MCP changelog](https://github.com/ChromeDevTools/chrome-devtools-mcp/blob/main/CHANGELOG.md).

Therefore Hermes can already expose raw WebMCP through Chrome DevTools MCP if an operator configures that server and flag. That path does **not** supply the bridge's required capability firewall, opaque lifecycle-bound IDs, origin allowlist, exact-argument approval binding, or output/redaction policy. The raw MCP tools should not be enabled alongside the bridge on a locked-down profile, because they provide a policy bypass.

There is also a known upstream timeout/cancellation concern: an unresolved page tool has been observed to hold Chrome DevTools MCP's tool lock, with cancellation not reaching the page tool. The bridge needs its own bounded deadline, must mark a timed-out mutating call as `outcome_uncertain`, and must never retry it automatically. Source: [Chrome DevTools MCP issue #2934](https://github.com/ChromeDevTools/chrome-devtools-mcp/issues/2934).

## 4. Cloudflare Browser Run WebMCP

Cloudflare Browser Run provides two WebMCP-capable backends:

- Chrome Lab: request `lab=true`; Cloudflare calls this experimental and says it is not for production workloads.
- Kitesurf: add `browser=kitesurf` to the Browser Run CDP URL.

Both expose a WebMCP CDP domain usable by CDP clients and Chrome DevTools MCP. Cloudflare's documented Chrome DevTools MCP command supplies the remote `wss://` endpoint, authorization headers, and `--category-experimental-webmcp`/current equivalent to add listing and execution tools. Source: [Cloudflare Browser Run WebMCP](https://developers.cloudflare.com/browser-run/features/webmcp/).

Cloudflare documents material backend differences. Kitesurf does not implement WebMCP's `tools` permissions policy or origin filtering, does not expose iframe/popup tools through CDP, and has no live view for confirming tools that wait on human interaction. Those gaps make the plugin's own origin and approval checks mandatory; Kitesurf should not be used for the booking-confirmation portion of the demo. Source: [Cloudflare WebMCP limitations](https://developers.cloudflare.com/browser-run/features/webmcp/#limitations).

Remote CDP endpoints must be `wss://`. Authorization headers are secrets and may be used only in the transport setup, never echoed in tool output, logs, endpoint identity, exceptions, or capability IDs. The configured host must be explicitly allowlisted; URL input passed by the model must not be accepted as a connection endpoint.

## 5. Cloudflare's WebMCP adapter

Cloudflare's `agents/experimental/webmcp` adapter does the opposite direction from this plugin: it discovers a remote `McpAgent` over MCP, registers shims into the page's WebMCP registry, watches `tools/list_changed`, and disposes registrations and transport with an abortable lifecycle. It is useful reference code for refresh coalescing and teardown, not a transport for discovering arbitrary page-local tools from Hermes. Source: [Cloudflare Agents WebMCP adapter](https://github.com/cloudflare/agents/blob/main/experimental/webmcp.md).

Reusable ideas:

- coalesce concurrent refreshes;
- make disposal idempotent;
- cancel in-flight discovery/execution on disposal;
- listen for tool-list changes where the backend exposes them;
- treat description/schema as data copied from an untrusted producer.

Non-reusable assumptions: the adapter runs inside a browser, flattens MCP results into strings, and intentionally has no per-tool filtering/permission layer.

## 6. Existing CDP bridges

`littleplato/webmcp-cdp-bridge` is a small Bun/TypeScript stdio MCP server. It fetches `http://localhost:9222/json`, selects the first page (or a URL substring), uses `Runtime.evaluate` to call the in-page model-context API, and refreshes on every `tools/list`. Its own README lists first-tab selection and localhost development mode as limitations. Source: [littleplato/webmcp-cdp-bridge](https://github.com/littleplato/webmcp-cdp-bridge).

What can be reused conceptually: thin CDP request/reply mechanics and refresh-on-list. What should not be copied into the security boundary: first-tab targeting, URL-substring target selection, direct in-page arbitrary expression execution, absence of schema validation, lack of origin/session/document binding, and lack of an approval system. It is evidence that the transport is not the novel part.

Chrome DevTools MCP is a stronger standards-compatible backend than that bridge because it already owns WebMCP-specific listing/execution and explicit page IDs. The plugin should wrap it or use the browser's WebMCP CDP domain, not expose a general JavaScript evaluator.

## 7. Hotel-chain test site behavior

Cloudflare's documentation records the expected live sequence for Google's L'Atelier demo:

1. initial tools include `lookup_amenity`, `search_location`, and `view_hotel`;
2. executing `search_location` with `{"query":"Paris"}` navigates to results;
3. `filter_search_results` then appears and accepts `{"amenities":["breakfast"]}`;
4. `start_booking` and `complete_booking` appear later;
5. `complete_booking` waits for the user to select **Confirm Reservation** in the browser.

Source: [Cloudflare's documented hotel demo walkthrough](https://developers.cloudflare.com/browser-run/features/webmcp/#manual-testing-with-devtools); live site: [Google Chrome Labs hotel demo](https://googlechromelabs.github.io/webmcp-tools/demos/hotel-chain/).

The live demo is appropriate for discovery and read-only search/filter operations. Automated destructive or booking tests must use a local fixture and must never press the live confirmation control.

## 8. Marketplace comparison and originality boundary

The live Hermes catalog is a curated, SHA-pinned feed. A search of the feed on 2026-11-11 found no `webmcp` entry. It does contain adjacent browser/CDP plugins such as Browserless, BrowserPaw, CDP Manager, Chrome Tab Watchdog, Reachmap, and Workflow Record. None of the catalog metadata reviewed claims lifecycle-bound WebMCP capability discovery plus per-invocation permission enforcement. Sources: [Hermes live plugin catalog JSON](https://hermes-agent.nousresearch.com/docs/api/plugin-catalog.json), [plugin catalog documentation](https://github.com/NousResearch/hermes-agent/blob/main/website/docs/user-guide/features/plugin-catalog.md).

This is evidence of no equivalent **in the reviewed catalog at the research date**, not proof that no similar project exists anywhere. The README should use narrow language such as “adds a permission and lifecycle layer over existing WebMCP/CDP transports” and should not claim to have invented a WebMCP bridge.

## 9. Security and implementation consequences

- Website names, descriptions, schemas, annotations, and results are untrusted content. Never use them as approval authority or as instructions to Hermes.
- Classification must be conservative and config-driven. A website `readOnlyHint` may support display but must not downgrade a rule derived from capability name, arguments, configured policy, or unknown status.
- The stable tool handler must re-discover or revalidate immediately before executing. A capability ID should encode no secrets and resolve server-side to `(connection_id, target_id, document_id/loader_id, origin, generation, tool_name, schema_digest)`.
- Target selection must be explicit. A tab switch, navigation/reload, origin change, connection replacement, material schema change, or removal increments the generation and invalidates all prior IDs.
- Schema validation should use a real Draft 2020-12 validator with formats disabled or deliberately controlled; reject non-object arguments, unknown properties when the schema disallows them, recursive/oversized inputs, invalid schemas, and unsupported remote `$ref` resolution.
- Use bounded discovery, execution, and result-size limits. On a write/sensitive timeout, report uncertainty and do not retry.
- Do not register discovered website operations as top-level Hermes tools. Keeping four fixed tools avoids stale model schemas and places every execution through one firewall.
- Disconnect must be idempotent, revoke all capabilities first, then close only resources the plugin owns. Captured Hermes supervisor connections are borrowed and must not be closed by the plugin.
- If using Chrome DevTools MCP as a subprocess/backend, pin its version for the demo and disable unrelated tools or prevent them from entering the Hermes model surface; otherwise `execute_webmcp_tool` is a bypass around `webmcp_execute`.

## 10. Recommended claim for the submission

“Hermes WebMCP Guard reuses WebMCP support in modern CDP/Chrome DevTools tooling and adds a Hermes-native capability firewall: stable discovery/execution tools, conservative operation classes, exact one-invocation approvals, origin and document binding, stale-capability rejection, bounded execution, and safe teardown.”

That claim is supported by the sources above and avoids overstating originality.
