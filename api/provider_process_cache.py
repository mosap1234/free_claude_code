"""Process-level provider cache for scripts and unit tests only.

HTTP request handlers MUST use ``request.app.state.provider_registry`` installed by
:class:`api.runtime.AppRuntime` via :func:`api.dependencies.resolve_provider` with
a non-null ``app``. This module retains a standalone cache only for ``app=None``
call paths (offline scripts, synchronous tests).

Always access the cache as ``provider_process_cache.PROCESS_PROVIDERS`` (module
attribute) so tests can rebind it for isolation.

``cleanup_process_providers()`` builds ``ProviderRegistry(PROCESS_PROVIDERS)`` and
runs :meth:`~providers.registry.ProviderRegistry.cleanup`, which clears the
injected provider mapping **in place**. Rebinding only ``PROCESS_PROVIDERS = {}``
after import does not detach registries/tests that still hold references to the
previous dict instance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from providers.registry import ProviderRegistry

if TYPE_CHECKING:
    from providers.base import BaseProvider

PROCESS_PROVIDERS: dict[str, BaseProvider] = {}


async def cleanup_process_providers() -> None:
    """Close cached providers and clear :data:`PROCESS_PROVIDERS` in place."""
    await ProviderRegistry(PROCESS_PROVIDERS).cleanup()
