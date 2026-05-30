"""Regression tests for tool_call ``index`` handling in ``_process_tool_call``.

Gemini's OpenAI-compatible streaming emits tool_call deltas where ``index`` is
an explicit ``null`` (the key is present with value ``None``) rather than an
integer. ``dict.get("index", 0)`` returns ``None`` for an explicit null -- the
default only applies to a *missing* key -- so the downstream ``if tc_index < 0``
raised::

    TypeError: '<' not supported between instances of 'NoneType' and 'int'

A simple text response never hits this path, which is why the symptom was
"plain replies work but any tool call crashes" on Gemini. The fix coerces a
``None`` index to ``0`` before the comparison.
"""

import json
from unittest.mock import MagicMock

from config.nim import NimSettings
from core.anthropic import ContentBlockManager
from providers.base import ProviderConfig
from providers.nvidia_nim import NvidiaNimProvider


# ``_process_tool_call`` lives on the shared ``OpenAIChatTransport`` base, so any
# concrete subclass exercises it; NvidiaNimProvider is the lightest to build.
def _provider() -> NvidiaNimProvider:
    return NvidiaNimProvider(ProviderConfig(api_key="test"), nim_settings=NimSettings())


def _sse() -> MagicMock:
    sse = MagicMock()
    sse.blocks = ContentBlockManager()
    return sse


def test_process_tool_call_handles_null_index():
    """A delta with ``index: None`` (Gemini) must not raise and lands at 0."""
    provider = _provider()
    sse = _sse()

    tc = {
        "index": None,  # Gemini openai-compat sends an explicit null here
        "id": "tool_123",
        "function": {"name": "Read", "arguments": json.dumps({"file_path": "x.py"})},
    }

    # Before the fix this raised TypeError on ``None < 0``.
    list(provider._process_tool_call(tc, sse))

    # The null index is coerced to 0, so the tool block is registered at index 0.
    assert 0 in sse.blocks.tool_states
    assert sse.start_tool_block.call_args[0][0] == 0


def test_process_tool_call_missing_index_defaults_to_zero():
    """An absent ``index`` key keeps the pre-existing default-to-0 behavior."""
    provider = _provider()
    sse = _sse()

    tc = {
        "id": "tool_456",
        "function": {"name": "Read", "arguments": "{}"},
    }

    list(provider._process_tool_call(tc, sse))

    assert 0 in sse.blocks.tool_states


def test_process_tool_call_preserves_integer_index():
    """A normal integer index (OpenAI-spec providers) is untouched."""
    provider = _provider()
    sse = _sse()

    tc = {
        "index": 2,
        "id": "tool_789",
        "function": {"name": "Read", "arguments": "{}"},
    }

    list(provider._process_tool_call(tc, sse))

    assert 2 in sse.blocks.tool_states
    assert sse.start_tool_block.call_args[0][0] == 2
