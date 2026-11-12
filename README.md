# Hermes WebMCP Guard

[![CI](https://github.com/NifasathA/hermes-webmcp-guard/actions/workflows/ci.yml/badge.svg)](https://github.com/NifasathA/hermes-webmcp-guard/actions/workflows/ci.yml)

Hermes WebMCP Guard is an installable Hermes Agent plugin that discovers and invokes website-provided WebMCP tools while treating every website capability as temporary and untrusted.

It reuses Chrome's native `WebMCP` CDP domain. The contribution is the firewall around that transport: explicit endpoints and origins, strict schemas, READ/WRITE/SENSITIVE classification, exact one-call approvals, document-bound IDs, bounded execution, redaction, and safe revocation.

## Status

The Python implementation and Raspberry Pi 5 live-browser flows have been verified with Hermes 0.23.1 and Chromium Shell 156. The deterministic suite passes 24 tests with the opt-in live test skipped; the live hotel-chain test passes separately when its CDP endpoint is supplied. WebMCP remains experimental.

## How it differs

| Existing approach | What it provides | What this plugin adds |
|---|---|---|
| Chrome DevTools MCP | Raw `list_webmcp_tools` / `execute_webmcp_tool` transport | Origin and lifecycle binding, conservative policy, exact approval, validation, redaction |
| Generic CDP bridges | Page-to-MCP connectivity, sometimes via page JavaScript | Native WebMCP CDP only, explicit target selection, no arbitrary JS tool, stale-ID rejection |
| Hermes browser automation | General clicking, extraction, screenshots, raw CDP | Structured website operations through four fixed tools and one mandatory firewall |

Do not enable raw Chrome DevTools MCP WebMCP execution tools alongside this plugin on a locked-down profile; they would be an alternate path around the firewall.

## Install

Requirements: Python 3.11+, a current Hermes release with `pre_tool_call` approval directives, and a WebMCP-enabled Chromium 149+ CDP backend.

```bash
git clone https://github.com/NifasathA/hermes-webmcp-guard.git
cd hermes-webmcp-guard
python -m pip install -e '.[test]'
hermes plugins doctor .
hermes plugins enable hermes-webmcp-guard
```

The editable install publishes the `hermes_agent.plugins` entry point. The root `__init__.py` also supports Hermes directory-plugin loading.

## Configure

Add this under `plugins.entries.hermes-webmcp-guard` in `~/.hermes/config.yaml` (see `config.example.yaml`):

```yaml
plugins:
  enabled:
    - hermes-webmcp-guard
  entries:
    hermes-webmcp-guard:
      settings:
        endpoints:
          hotel-demo:
            websocket_url: ws://127.0.0.1:9222/devtools/page/REPLACE_TARGET
            allowed_origins:
              - https://googlechromelabs.github.io
            execution_timeout_seconds: 20
            max_response_bytes: 262144
```

The model can name only `hotel-demo`; it cannot supply a URL. A page endpoint is used directly. For a browser-level endpoint, the bridge attaches only if exactly one page target has an allowed origin, or trusted configuration pins `target_id`. Remote endpoints must use `wss://`. Credential-bearing endpoint URLs and header configuration are rejected; terminate authenticated remote CDP connections through a trusted local proxy and configure its loopback WebSocket URL.

## Run the local safety fixture

Start the fixture:

```bash
cd hermes-webmcp-guard
python -m http.server 8765 --directory demo/fixture-site
```

In another terminal, start a compatible Chromium build:

```bash
chromium \
  --remote-debugging-port=9222 \
  --remote-allow-origins=http://127.0.0.1:9222 \
  --user-data-dir=/tmp/hermes-webmcp-profile \
  --enable-features=WebMCPTesting,DevToolsWebMCPSupport \
  http://127.0.0.1:8765
```

On Linux ARM64, regular Chromium 151+ may hang on HTTP(S) navigation because of
[upstream Chromium issue 554752968](https://issues.chromium.org/issues/554752968).
Use the distribution's dedicated `chromium-shell` package as the browser binary
when that minimized navigation check fails; it exposes the same CDP/WebMCP
domain without the affected browser embedder.

Get the exact page WebSocket and place it in the configured endpoint:

```bash
python -c 'import json,urllib.request; pages=json.load(urllib.request.urlopen("http://127.0.0.1:9222/json/list")); print(next(x["webSocketDebuggerUrl"] for x in pages if x["type"] == "page" and x["url"].startswith("http://127.0.0.1:8765")))'
```

Restart Hermes after configuration changes:

```bash
hermes chat
```

Suggested prompts:

```text
Connect WebMCP to the configured endpoint local-fixture and list the available capabilities.
Execute list_records.
Execute delete_record for demo-1. Do not approve it when prompted.
Disconnect this website.
```

The fixture never performs external writes. `delete_record` deliberately lies with `readOnlyHint: true`; the bridge still classifies it as SENSITIVE.

## Hotel demo

Open `https://googlechromelabs.github.io/webmcp-tools/demos/hotel-chain/` in the configured WebMCP browser, then run:

```text
Connect to hotel-demo and tell me what WebMCP actions are available.
Use the structured capability to search for Paris.
Refresh the WebMCP capabilities and filter for breakfast.
```

Expected upstream sequence: initial `lookup_amenity`, `search_location`, and `view_hotel`; `filter_search_results` appears after the Paris search. Booking operations require firewall approval and the site's own confirmation. Do not complete a real or public-demo booking in automated tests.

The exact video flow is in `demo/demo-script.md`.

### Verified live environment

On 2026-11-11, the opt-in hotel test passed on Raspberry Pi host `booga-pi` using Hermes Agent 0.23.1, Python 3.13.5, and Debian Chromium Shell 156.0.8000.49. It discovered the expected initial capabilities, searched Paris, observed `filter_search_results` appear dynamically, and filtered for breakfast. No booking capability was invoked. The exact reproducible test is `tests/test_integration.py::test_live_hotel_discovery_search_and_dynamic_filter`.

## Tools

- `webmcp_connect`: attach to a named configured endpoint and report session/tab/document/origin/status/count.
- `webmcp_list_tools`: return machine-readable schemas, annotations, risk, origin, scope, and opaque IDs.
- `webmcp_execute`: revalidate arguments and lifecycle, then invoke through the firewall.
- `webmcp_disconnect`: revoke first, close owned resources, and remain idempotent.

WRITE, SENSITIVE, unknown, and ambiguous tools use Hermes's supported `{"action":"approve"}` directive. Approval is additionally bound to owner, unique `tool_call_id`, capability, and canonical validated arguments, then consumed once. If Hermes omits the call ID, execution fails closed.

## Test

```bash
cd hermes-webmcp-guard
python -m pytest
```

The default suite uses a deterministic simulated CDP/WebMCP adapter. It covers discovery, unsupported pages, malformed schemas/arguments, changing tools, origins, expiration, stale IDs, unauthorized origins, deceptive annotations, approval denial/success/replay, uncertain timeouts, disconnection, concurrency, prompt injection, and redaction.

The live test is opt-in and intentionally skipped otherwise:

```bash
WEBMCP_LIVE_CDP_URL='wss://…' python -m pytest -m live -vv
```

That smoke test only verifies explicit setup today; follow `demo/demo-script.md` for the real hotel sequence and record its output before marketplace submission.

## Security notes

- Website metadata and output are labeled untrusted and never treated as policy.
- Capability IDs contain hashes, not credentials.
- Timeouts return `outcome_uncertain: true`; the plugin never retries.
- Browser permission and website confirmation UI remain authoritative.
- The plugin does not silently capture or launch a second Hermes browser. Current Hermes supervisor capture lacks the authoritative WebMCP event subscription this adapter needs, so v0.1 uses an explicit connection and says so.

See `docs/research.md`, `docs/architecture.md`, and `docs/threat-model.md` for evidence and boundaries. `docs/benchmark.md` explains why no unsupported quantitative claim is included.

## License

MIT

