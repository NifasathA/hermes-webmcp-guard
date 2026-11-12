from __future__ import annotations

import os
import time

import pytest

from hermes_webmcp_guard.browser_adapter import CDPWebMCPAdapter
from hermes_webmcp_guard.models import EndpointConfig


@pytest.mark.skipif(not os.environ.get("WEBMCP_LIVE_CDP_URL"), reason="live WebMCP CDP endpoint not configured; not reported as passing")
@pytest.mark.live
def test_live_hotel_discovery_search_and_dynamic_filter():
    """Real read-only flow; the operator must open the hotel demo before running."""
    url = os.environ["WEBMCP_LIVE_CDP_URL"]
    headers = {}
    if os.environ.get("WEBMCP_LIVE_AUTHORIZATION"):
        headers["Authorization"] = os.environ["WEBMCP_LIVE_AUTHORIZATION"]
    adapter = CDPWebMCPAdapter(EndpointConfig(
        "live", url, ("https://googlechromelabs.github.io",), headers=headers,
        connect_timeout_seconds=15, execution_timeout_seconds=30,
    ))
    adapter.connect()
    try:
        initial = {tool.name: tool for tool in adapter.list_tools()}
        assert {"lookup_amenity", "search_location", "view_hotel"} <= set(initial)
        adapter.execute(initial["search_location"], {"query": "Paris"})
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            current = {tool.name: tool for tool in adapter.list_tools()}
            if "filter_search_results" in current:
                break
            time.sleep(0.1)
        else:
            pytest.fail("filter_search_results did not appear after navigation")
        output = adapter.execute(current["filter_search_results"], {"amenities": ["breakfast"]})
        assert output is not None
    finally:
        adapter.disconnect()

