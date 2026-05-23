"""Guard catalog ``openai_request_module`` strings used by dynamic imports."""

from __future__ import annotations

import importlib.util

from config.provider_catalog import PROVIDER_CATALOG


def test_openai_request_modules_resolve_under_providers() -> None:
    """Every dynamic OpenAI-compat request builder must live under ``providers.*``."""
    for pid, desc in PROVIDER_CATALOG.items():
        if desc.openai_request_module is None:
            continue
        path = desc.openai_request_module
        assert path.startswith("providers."), (
            f"{pid}: openai_request_module must start with 'providers.', got {path!r}"
        )
        assert "/" not in path and "\\" not in path, (
            f"{pid}: dotted module path only, got {path!r}"
        )
        spec = importlib.util.find_spec(path)
        assert spec is not None, f"{pid}: cannot resolve import spec for {path!r}"
