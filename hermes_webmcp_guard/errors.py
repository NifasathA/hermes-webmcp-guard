"""Stable error types returned by the bridge."""


class WebMCPError(Exception):
    code = "WEBMCP_ERROR"


class ConfigurationError(WebMCPError):
    code = "CONFIGURATION_ERROR"


class ConnectionRejected(WebMCPError):
    code = "CONNECTION_REJECTED"


class BackendDisconnected(WebMCPError):
    code = "BACKEND_DISCONNECTED"


class CapabilityStale(WebMCPError):
    code = "CAPABILITY_STALE"


class OriginDenied(WebMCPError):
    code = "ORIGIN_DENIED"


class SchemaRejected(WebMCPError):
    code = "SCHEMA_REJECTED"


class ArgumentsRejected(WebMCPError):
    code = "ARGUMENTS_REJECTED"


class ApprovalRequired(WebMCPError):
    code = "APPROVAL_REQUIRED"


class ExecutionUncertain(WebMCPError):
    code = "EXECUTION_UNCERTAIN"

