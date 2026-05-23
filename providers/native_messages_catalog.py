"""Catalog inventory for native Anthropic Messages HTTP transports.

Roadmap: ``providers/notes/native_anthropic_http_providers.md`` (IMPROVEMENT_PLAN Phase 3b).

Enumerates catalog rows that share
:class:`~providers.anthropic_messages.AnthropicMessagesTransport` without importing
per-adapter client modules.
"""

from __future__ import annotations

from config.provider_catalog import PROVIDER_CATALOG


def native_anthropic_messages_provider_ids() -> frozenset[str]:
    """Return ids for rows using the native Anthropic Messages HTTP transport."""
    return frozenset(
        pid
        for pid, desc in PROVIDER_CATALOG.items()
        if desc.transport_type == "anthropic_messages"
    )
