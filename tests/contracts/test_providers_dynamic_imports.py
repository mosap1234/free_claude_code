"""Contract for intentional ``importlib`` / dynamic imports under ``providers/``.

:class:`~providers.openai_chat_adapter.CatalogOpenAIChatProvider` loads
``build_request_body`` via :func:`importlib.import_module`; all other modules must
stay static-import only.
"""

from __future__ import annotations

from pathlib import Path

_ALLOWED_PROVIDER_IMPORTLIB_MODULES = frozenset(
    {
        Path("providers") / "openai_chat_adapter.py",
    },
)


def test_providers_dynamic_import_allowlist() -> None:
    """Only allowlisted modules may call ``importlib.import_module`` / ``__import__``."""

    repo_root = Path(__file__).resolve().parents[2]
    offenders: list[str] = []
    for path in (repo_root / "providers").rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        rel_path = path.relative_to(repo_root)
        lines = path.read_text(encoding="utf-8").splitlines()
        for idx, raw in enumerate(lines, start=1):
            stripped = raw.strip()
            if stripped.startswith("#"):
                continue
            if (
                "importlib.import_module" not in stripped
                and "__import__(" not in stripped
            ):
                continue
            if rel_path not in _ALLOWED_PROVIDER_IMPORTLIB_MODULES:
                offenders.append(f"{rel_path}:{idx}:{stripped}")
    assert sorted(offenders) == []


def test_api_package_has_no_dynamic_provider_import_patterns() -> None:
    """``api`` must not dynamically load ``providers.*`` modules."""

    repo_root = Path(__file__).resolve().parents[2]
    offenders: list[str] = []
    for path in (repo_root / "api").rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        rel_path = path.relative_to(repo_root)
        for idx, raw in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        ):
            stripped = raw.strip()
            if stripped.startswith("#"):
                continue
            if (
                "import_module" not in stripped and "__import__" not in stripped
            ) or "providers." not in stripped:
                continue
            offenders.append(f"{rel_path}:{idx}:{stripped}")
    assert sorted(offenders) == []
