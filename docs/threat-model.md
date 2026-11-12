# Threat model

## Protected assets

User accounts and external state, browser credentials, CDP authorization headers, integrity of the user's approval, and separation among Hermes sessions, tabs, documents, and origins.

## Adversaries

A malicious or compromised website may register deceptive names, descriptions, annotations, schemas, and results; change its tool set around navigation; replay a prior capability; hang after beginning a mutation; or include prompt injection and secrets in output. A model may supply malformed arguments or attempt to connect to an internal service.

## Controls

| Threat | Control |
|---|---|
| SSRF / metadata access | The model supplies a configured endpoint name, never a URL. Remote endpoints require `wss://`; metadata, private, and link-local IPs are rejected. Loopback `ws://` is allowed only as explicit operator configuration. |
| Wrong tab/origin | Browser-level target selection requires exactly one allowed-origin page or a configured target ID. Every discovery and execution rechecks the origin. |
| Stale/cross-origin reuse | IDs bind session, tab, loader/document, origin, frame, schema, and generation. Any relevant change revokes them. |
| Deceptive `readOnlyHint` | Website annotations and descriptions never downgrade risk. Unknown operations require approval. |
| Approval replay | A one-use intent binds Hermes owner, `tool_call_id`, capability, and validated argument digest; it is consumed once. Missing call IDs fail closed. |
| Invalid input/schema | Draft 2020-12 validation, object roots, bounded depth/nodes, and no remote reference fetch. |
| Prompt injection | External metadata and results are labeled untrusted data. Website prose is never executed as plugin policy. |
| Secret disclosure | Transport headers come from environment variables; endpoint URLs cannot contain credentials; secret-shaped output keys are redacted; errors are bounded. |
| Hanging mutation | Finite deadline, best-effort CDP cancellation, explicit `outcome_uncertain`, and no automatic retry. |
| Oversized output | Configurable byte cap before returning content to Hermes. |
| Browser permission bypass | Only native `WebMCP.invokeTool` is used; website confirmation UI and browser permission checks remain in force. |
| Policy bypass through raw MCP | Deployment guidance requires disabling raw Chrome DevTools MCP WebMCP tools on locked-down profiles. |

## Residual risks

Classification is heuristic and intentionally over-approves; a benign obscure read tool may require confirmation. Website results can contain sensitive values under non-obvious keys. Python plugins run in Hermes's process and are trusted code, not a sandbox. A browser may complete a mutation before a connection loss or timeout becomes observable. WebMCP/CDP compatibility can change while the standards are experimental.

