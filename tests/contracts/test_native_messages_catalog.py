"""Inventory helpers for native Anthropic Messages catalog rows."""

from __future__ import annotations

from config.provider_catalog import PROVIDER_CATALOG
from providers.native_messages_catalog import native_anthropic_messages_provider_ids


def test_native_anthropic_messages_ids_mirror_catalog_filter() -> None:
    expected = frozenset(
        pid
        for pid, desc in PROVIDER_CATALOG.items()
        if desc.transport_type == "anthropic_messages"
    )
    assert native_anthropic_messages_provider_ids() == expected
