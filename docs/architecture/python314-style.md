# Python 3.14 style notes (repo tooling)

This project targets **Python 3.14** with **Ruff** `target-version = "py314"` (see [`pyproject.toml`](../../pyproject.toml) and [AGENTS.md](../../AGENTS.md)).

## Annotations / PEP 649 vs PEP 563

- **[PEP 649](https://peps.python.org/pep-0649/)** (deferred evaluation) is how annotations behave **by default** in Python 3.14 for modules that do **not** use `from __future__ import annotations`. That replaces the historic need for that future import in most forward-reference cases.
- **`from __future__ import annotations`** opts into **[PEP 563](https://peps.python.org/pep-0563/)**: annotations are compiled to **strings** in `__annotations__`. Those semantics differ from PEP 649. This codebase **does not** use that import (CI greps forbid it): see repo policy in [AGENTS.md](../../AGENTS.md).
- **[PEP 749](https://peps.python.org/pep-0749/)** describes how the language phases out the future import over a long timeline; do not assume CPython has removed or no-op’d it in 3.14.

Ruff’s semantic model for `py314` treats annotation checking similarly to deferred evaluation (see upstream Ruff discussions around 3.14 / PEP 649). If a third-party tool **inspects** annotations as concrete runtime values (e.g. certain `inspect` / mock paths), prefer `annotationlib` / string or forward-ref formats where appropriate rather than reintroducing `__future__.annotations`.

## Multi-exception `except`

**Intentionally valid in this codebase:** omitting parentheses when catching multiple exceptions:

```python
except TimeoutError, asyncio.CancelledError:
    ...
```

This matches [AGENTS.md](../../AGENTS.md) *Coding Environment* (Ruff/py314 formatter support). Automated reviewers or parsers that assume older Python 3 grammar may report false positives; prefer checking `uv run ruff format` / `uv run pytest` locally.

Do **not** mass-rewrite comma-style clauses to **`except (A, B):`** for “compat” unless the toolchain or supported Python band changes.
