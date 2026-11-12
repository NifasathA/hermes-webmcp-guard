# Benchmark status

No quantitative browser-UI-versus-WebMCP performance claim is included in this submission snapshot. A WebMCP-capable live browser endpoint was not available in the build environment, so measuring only a mocked transport would not satisfy the identical-task criterion.

The reproducible benchmark protocol is:

1. Fresh browser profile, same Chromium build, hotel demo loaded.
2. Task: find a Paris hotel with breakfast and report the first matching hotel; do not book.
3. Run A with Hermes browser UI automation only and record Hermes tool calls, monotonic wall time, success, errors/retries, and state-changing calls.
4. Reset the profile. Run B through the bridge (`search_location`, refresh, `filter_search_results`) and record the same fields.
5. Keep raw logs and report medians only after at least five successful trials per approach.

Until those live trials run, the project makes only structural claims: structured calls carry validated arguments and the bridge blocks unapproved state changes.

