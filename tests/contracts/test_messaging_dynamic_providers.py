from __future__ import annotations

from pathlib import Path


def test_messaging_tree_has_no_dynamic_provider_import_patterns() -> None:
    """Messaging must never load ``providers.*`` through importlib / __import__."""

    repo_root = Path(__file__).resolve().parents[2]
    messaging_root = repo_root / "messaging"

    offenders: list[str] = []
    for path in messaging_root.rglob("*.py"):
        lines = path.read_text(encoding="utf-8").splitlines()
        for idx, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if (
                "import_module" in line or "__import__" in line
            ) and "providers." in line:
                rel = path.relative_to(repo_root)
                offenders.append(f"{rel}:{idx}:{stripped}")

    assert offenders == []
