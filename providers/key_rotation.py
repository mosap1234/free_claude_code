"""Multi-API-key rotation utilities for distributing requests across keys.

When users configure comma-delimited API keys (e.g. ``NVIDIA_NIM_API_KEY="key1,key2,key3"``),
the provider transports rotate through them round-robin to avoid per-key rate limits.

All cloud providers in this project issue keys that are alphanumeric / hex / base64
with no commas, so comma-delimiting is safe.  Local providers (LM Studio, llama.cpp,
Ollama) use ``static_credential`` and never enter rotation paths.
"""

from __future__ import annotations

import itertools
from collections.abc import Sequence


def parse_api_keys(value: str) -> list[str]:
    """Split a comma-delimited API key string into a list of individual keys.

    Whitespace around each key is stripped and empty entries are removed so
    that trailing commas or extra spaces are harmless.

    Examples::

        >>> parse_api_keys("abc")
        ['abc']
        >>> parse_api_keys("abc, def ,ghi")
        ['abc', 'def', 'ghi']
        >>> parse_api_keys("  ")
        []
        >>> parse_api_keys("")
        []
    """
    if not value or not value.strip():
        return []
    return [k.strip() for k in value.split(",") if k.strip()]


class KeyRotator:
    """Round-robin key selector that cycles through a list of API keys.

    Thread-safe under CPython's GIL because ``itertools.count.__next__``
    is a C-level atomic operation, and asyncio's single-event-loop model
    serialises coroutines between ``await`` points.
    """

    def __init__(self, keys: Sequence[str]) -> None:
        if not keys:
            raise ValueError("KeyRotator requires at least one key")
        self._keys: list[str] = list(keys)
        self._counter = itertools.count()

    def next_key(self) -> str:
        """Return the next key in round-robin order."""
        index = next(self._counter) % len(self._keys)
        return self._keys[index]

    @property
    def primary_key(self) -> str:
        """Return the first (primary) key."""
        return self._keys[0]

    @property
    def all_keys(self) -> tuple[str, ...]:
        """Return all configured keys."""
        return tuple(self._keys)

    def __len__(self) -> int:
        return len(self._keys)
