"""Guardrails that referenced architecture markdown files ship in the repo."""

from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[2]
_DOCS_ARCH = _REPO / "docs" / "architecture"


@pytest.mark.parametrize(
    "relative",
    (
        "admin.md",
        "api-package.md",
        "deferred_milestones.md",
        "layers.md",
        "messaging.md",
        "STATUS.md",
        "IMPROVEMENT_PLAN.md",
    ),
)
def test_architecture_doc_file_exists(relative: str) -> None:
    path = _DOCS_ARCH / relative
    assert path.is_file(), f"missing {path.relative_to(_REPO)}"
