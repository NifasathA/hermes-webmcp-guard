# Under-90-second demo script

Prerequisite: start a WebMCP-capable Chrome Lab/Kitesurf session or Chromium with WebMCP enabled, open the hotel demo, and configure its CDP endpoint as `hotel-demo` with origin `https://googlechromelabs.github.io`.

0–10s: “This is Hermes WebMCP Guard. It reuses native WebMCP over CDP, but adds ephemeral capabilities and a permission firewall.”

10–20s: Ask: “Connect to `hotel-demo`. What WebMCP capabilities are available?” Show session, tab, document, origin, generation, and initial tools.

20–38s: Ask: “Search for Paris using WebMCP.” Hermes executes `search_location`. List again and highlight the new `filter_search_results` capability and changed generation.

38–50s: Ask: “Filter for breakfast.” Show the structured result without clicks or screenshots.

50–65s: Move to the local fixture. Ask to execute `delete_record`. Show that its deceptive `readOnlyHint` does not matter and Hermes requests approval. Deny it; fixture state stays unchanged.

65–78s: Approve one simulated sensitive call. Attempt the same capability again after reload; show `CAPABILITY_STALE` and no replay.

78–90s: Disconnect. Show `capabilities_revoked: true`. Close: “The bridge is the firewall and lifecycle layer—not a claim to have invented WebMCP transport.”

Never invoke booking completion on the public hotel demo. Use the fixture for approval and destructive-action shots.

