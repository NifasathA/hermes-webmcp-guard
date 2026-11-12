# Marketplace description

## Short description

Discover and invoke website WebMCP tools through Hermes with origin allowlists, strict schemas, conservative risk classification, exact one-call approvals, stale-capability rejection, and safe teardown.

## What makes it different

Chrome DevTools MCP and generic CDP bridges provide transport. Hermes browser automation provides flexible UI control. Hermes WebMCP Guard adds a narrow security and lifecycle layer over native WebMCP: four stable tools, opaque document-bound capability IDs, a firewall on every execution, and no arbitrary JavaScript surface.

## Submission checklist

- [x] `plugin.yaml` declares four tools and lifecycle hooks.
- [x] Python package and directory-plugin entry points both register with verified `ctx.register_tool` API.
- [x] Native event-driven WebMCP CDP adapter; page- and browser-level endpoints.
- [x] Explicit endpoint configuration, TLS/SSRF checks, origin allowlists, and rejection of credential-bearing configuration.
- [x] READ/WRITE/SENSITIVE policy independent of website annotations.
- [x] Hermes approval directive plus one-use exact-argument binding.
- [x] Session/tab/document/origin/generation invalidation.
- [x] Unit/integration-simulation tests; live test is explicitly opt-in and skipped otherwise.
- [x] Local no-network destructive-action fixture.
- [x] Research, architecture, threat model, demo, and benchmark protocol.
- [x] Run the live hotel demo on Raspberry Pi with Chromium Shell 156; read-only discovery/search/filter test passed.
- [ ] Record and publish the under-90-second video evidence.
- [x] Run `hermes plugins doctor` against Hermes 0.23.1.
- [x] Public repository and MIT license: https://github.com/NifasathA/hermes-webmcp-guard
- [ ] Add screenshots/video and immutable release tag.
