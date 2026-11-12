"""Directory-plugin compatibility wrapper for Hermes."""

# Hermes imports directory plugins as isolated packages, so the bundled
# implementation must be resolved relative to this wrapper.  Keep the absolute
# fallback for loading the source tree directly during development.
if __package__:
    from .hermes_webmcp_guard import register
else:
    from hermes_webmcp_guard import register

__all__ = ["register"]
