# Architecture

Hermes WebMCP Guard exposes four fixed Hermes tools and keeps every website operation behind `webmcp_execute`. It does not dynamically add website tools to Hermes.

```text
Hermes model
  -> webmcp_connect/list_tools/execute/disconnect
  -> capability firewall (schema + risk + exact approval)
  -> lifecycle store (session + tab + document + origin + generation)
  -> WebMCP CDP domain
  -> explicitly configured browser target
```

## Vertical slice

`CDPWebMCPAdapter` connects to a page WebSocket or a browser-level WebSocket. A browser-level connection attaches only when exactly one page target has an approved origin, unless trusted configuration pins `target_id`. It enables the native `WebMCP` domain before consuming the authoritative `toolsAdded` replay. It never exposes `Runtime.evaluate` or arbitrary JavaScript.

Discovery validates Draft 2020-12 object schemas, rejects pathological schemas, classifies each tool without trusting descriptions or annotations, and mints an opaque capability ID from session, tab, document, origin, generation, frame, name, and schema.

`pre_tool_call` validates the same capability and arguments. READ proceeds. WRITE, SENSITIVE, and unknown operations return Hermes's `approve` directive. An internal one-use intent is keyed by `tool_call_id` and binds owner, capability, and canonical argument digest. Official `tool_execution` middleware carries that call ID across Hermes's handler boundary after the approval gate; the handler consumes it once. Middleware failure cannot open the gate because a missing call ID blocks consequential execution. A persistent choice in a generic Hermes approval UI cannot authorize another tool call because its rule key includes a hash of the unique call ID.

Navigation and `toolsAdded/toolsRemoved` mark the catalog dirty without blocking the CDP receiver. The next boundary increments the generation and revokes old IDs. Disconnect revokes before closing. A timed-out operation is returned as uncertain and is never retried.

## Intentional limits

- Direct capture of a Hermes supervisor is not used in v0.1. The current public capture seam can send commands but does not expose the `WebMCP.toolsAdded` event stream needed for authoritative discovery. The plugin therefore requires an explicit endpoint and never claims it is the same session implicitly.
- WebMCP and its CDP domain are experimental. Pin a tested Chromium/Cloudflare Lab version for a demo.
- Kitesurf limitations documented by Cloudflare make it unsuitable for the human-confirmation portion of the demo.

