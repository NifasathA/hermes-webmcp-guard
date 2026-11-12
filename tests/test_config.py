import pytest

from hermes_webmcp_guard.config import parse_endpoints
from hermes_webmcp_guard.errors import ConfigurationError


@pytest.mark.parametrize("credential_field", ["headers", "headers_env"])
def test_endpoint_configuration_rejects_credentials(credential_field):
    endpoint = {
        "websocket_url": "ws://127.0.0.1:9222/devtools/page/example",
        "allowed_origins": ["https://example.com"],
        credential_field: {},
    }

    with pytest.raises(ConfigurationError, match="must not contain credentials"):
        parse_endpoints({"endpoints": {"example": endpoint}})
