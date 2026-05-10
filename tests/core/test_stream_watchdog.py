"""Tests for the stream silence watchdog."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import pytest

from core.stream_watchdog import (
    StreamSilentError,
    silence_timeout_s,
    stream_with_silence_watchdog,
)


async def _slow_stream(values: list[str], delays: list[float]) -> AsyncIterator[str]:
    for value, delay in zip(values, delays, strict=True):
        await asyncio.sleep(delay)
        yield value


@pytest.mark.asyncio
async def test_passes_through_fast_stream():
    """A stream that emits within the silence window passes through unchanged."""

    async def gen():
        yield "a"
        yield "b"
        yield "c"

    out = []
    async for chunk in stream_with_silence_watchdog(gen(), silence_timeout=0.5):
        out.append(chunk)
    assert out == ["a", "b", "c"]


@pytest.mark.asyncio
async def test_raises_on_silence():
    """Stream with a gap longer than the silence timeout raises."""

    async def slow():
        yield "a"
        await asyncio.sleep(1.0)
        yield "b"

    with pytest.raises(StreamSilentError) as exc_info:
        async for _chunk in stream_with_silence_watchdog(
            slow(), silence_timeout=0.1, request_id="test_req"
        ):
            pass
    assert "test_req" in str(exc_info.value)
    assert exc_info.value.silence_seconds >= 0.1


@pytest.mark.asyncio
async def test_zero_timeout_disables_watchdog():
    """silence_timeout <= 0 means pass-through, no watchdog."""

    async def slow():
        yield "a"
        await asyncio.sleep(0.05)
        yield "b"

    out = []
    async for chunk in stream_with_silence_watchdog(slow(), silence_timeout=0):
        out.append(chunk)
    assert out == ["a", "b"]


@pytest.mark.asyncio
async def test_silence_started_resets_after_each_chunk():
    """If chunks arrive within the timeout each time, no error fires.

    Streams gaps shorter than the timeout in sequence; total elapsed time
    exceeds the timeout but no individual gap does.
    """

    async def stream():
        for i in range(5):
            yield f"chunk_{i}"
            await asyncio.sleep(0.05)

    out = []
    async for chunk in stream_with_silence_watchdog(stream(), silence_timeout=0.15):
        out.append(chunk)
    assert len(out) == 5


@pytest.mark.asyncio
async def test_upstream_aclose_called_on_trip():
    """When the watchdog raises, the upstream iterator's aclose is called."""

    aclose_called = False

    class TrackingIterator:
        def __aiter__(self):
            return self

        async def __anext__(self):
            await asyncio.sleep(1.0)  # always sleep past the watchdog timeout
            return "never"

        async def aclose(self):
            nonlocal aclose_called
            aclose_called = True

    with pytest.raises(StreamSilentError):
        async for _ in stream_with_silence_watchdog(
            TrackingIterator(), silence_timeout=0.05
        ):
            pass
    assert aclose_called is True


def test_silence_timeout_env_default(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("NIM_STREAM_SILENCE_TIMEOUT_S", raising=False)
    assert silence_timeout_s() == 90.0


def test_silence_timeout_env_override_wins_over_tier(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("NIM_STREAM_SILENCE_TIMEOUT_S", "120")
    # Even an XL model uses the env override, not the tier default.
    assert silence_timeout_s("qwen/qwen3-coder-480b-a35b-instruct") == 120.0


def test_silence_timeout_env_invalid_falls_back(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NIM_STREAM_SILENCE_TIMEOUT_S", "garbage")
    assert silence_timeout_s() == 90.0


def test_silence_timeout_env_zero_disables(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NIM_STREAM_SILENCE_TIMEOUT_S", "0")
    assert silence_timeout_s() == 0.0


@pytest.mark.parametrize(
    "model, expected",
    [
        ("nvidia/nemotron-3-nano-30b-a3b", 45.0),
        ("openai/gpt-oss-20b", 45.0),
        ("qwen/qwen3-next-80b-a3b-instruct", 60.0),
        ("meta-llama/llama-3.3-70b-instruct", 60.0),
        ("nvidia/nemotron-super-120b-a12b", 90.0),
        ("openai/gpt-oss-120b", 90.0),
        ("nvidia/llama-3.1-nemotron-ultra-253b-v1", 120.0),
        ("qwen/qwen3-coder-480b-a35b-instruct", 150.0),
        ("nousresearch/hermes-3-llama-3.1-405b", 150.0),
        ("mistralai/mistral-large-3-675b-instruct-2512", 180.0),
    ],
)
def test_silence_timeout_tier_aware_defaults(
    monkeypatch: pytest.MonkeyPatch, model: str, expected: float
):
    monkeypatch.delenv("NIM_STREAM_SILENCE_TIMEOUT_S", raising=False)
    assert silence_timeout_s(model) == expected


def test_silence_timeout_unknown_model_uses_global_default(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("NIM_STREAM_SILENCE_TIMEOUT_S", raising=False)
    assert silence_timeout_s("unknown/random-model") == 90.0


def test_silence_timeout_no_model_uses_global_default(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.delenv("NIM_STREAM_SILENCE_TIMEOUT_S", raising=False)
    assert silence_timeout_s() == 90.0
    assert silence_timeout_s(None) == 90.0
