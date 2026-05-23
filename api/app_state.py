"""Documented Starlette/FastAPI ``app.state`` keys for the Claude proxy.

Runtime code still uses ordinary attribute assignment; these types are advisory for
refactoring (not enforced at assignment).
"""

from typing import TYPE_CHECKING, TypedDict

if TYPE_CHECKING:
    from providers.registry import ProviderRegistry


class ClaudeProxyAppState(TypedDict, total=False):
    """Optional attrs published by ``api.runtime.AppRuntime`` lifecycle."""

    provider_registry: ProviderRegistry
    """App-owned upstream cache populated during startup."""

    claude_proxy_runtime: object
    """Installed after successful messaging/provider startup."""

    messaging_platform: object
    message_handler: object
    cli_manager: object

    startup_validation_error: str
    """Set when startup model validation warns but keeps the server alive."""

    admin_restart_callback: object
    """Uvicorn/restart shim registered by the CLI server wrapper."""
