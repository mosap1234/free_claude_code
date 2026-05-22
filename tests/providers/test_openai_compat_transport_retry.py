"""Tests for mid-stream transport-error retry in OpenAIChatTransport."""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from config.nim import NimSettings
from providers.base import ProviderConfig
from providers.nvidia_nim import NvidiaNimProvider
from tests.providers.test_streaming_errors import (
    AsyncStreamMock,
    _collect_stream,
    _make_chunk,
    _make_provider,
    _make_request,
)
from tests.provider_request_mocks import make_openai_compat_stream_request


def _make_remote_protocol_error(message: str = "peer closed connection") -> httpx.RemoteProtocolError:
    """Create a RemoteProtocolError matching the NVIDIA NIM failure pattern."""
    return httpx.RemoteProtocolError(message)


def _make_read_error(message: str = "connection lost") -> httpx.ReadError:
    """Create a ReadError (another retryable transport error)."""
    return httpx.ReadError(message)


class TestTransportErrorRetry:
    """Mid-stream RemoteProtocolError triggers transparent retry (up to 2)."""

    @pytest.mark.asyncio
    async def test_remote_protocol_error_retries_once_and_succeeds(self):
        """First attempt fails with RemoteProtocolError, second succeeds."""
        provider = _make_provider()
        request = _make_request()

        chunk_ok = _make_chunk(content="Retry worked", finish_reason="stop")
        stream_ok = AsyncStreamMock([chunk_ok])

        with (
            patch.object(
                provider._client.chat.completions,
                "create",
                new_callable=AsyncMock,
                side_effect=[
                    _make_remote_protocol_error(),  # attempt 1 fails
                    stream_ok,                       # attempt 2 succeeds
                ],
            ),
            patch.object(
                provider._global_rate_limiter,
                "wait_if_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("providers.openai_compat.asyncio.sleep", new_callable=AsyncMock),
        ):
            events = await _collect_stream(provider, request)

        event_text = "".join(events)
        # The successful content from the retry should be present
        assert "Retry worked" in event_text
        assert "message_stop" in event_text
        # The error message should NOT be present (retry succeeded)
        assert "RemoteProtocolError" not in event_text

    @pytest.mark.asyncio
    async def test_remote_protocol_error_retries_twice_and_succeeds(self):
        """First two attempts fail, third succeeds."""
        provider = _make_provider()
        request = _make_request()

        chunk_ok = _make_chunk(content="Third time lucky", finish_reason="stop")
        stream_ok = AsyncStreamMock([chunk_ok])

        with (
            patch.object(
                provider._client.chat.completions,
                "create",
                new_callable=AsyncMock,
                side_effect=[
                    _make_remote_protocol_error("drop 1"),  # attempt 1 fails
                    _make_remote_protocol_error("drop 2"),  # attempt 2 fails
                    stream_ok,                                # attempt 3 succeeds
                ],
            ),
            patch.object(
                provider._global_rate_limiter,
                "wait_if_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("providers.openai_compat.asyncio.sleep", new_callable=AsyncMock),
        ):
            events = await _collect_stream(provider, request)

        event_text = "".join(events)
        assert "Third time lucky" in event_text
        assert "message_stop" in event_text

    @pytest.mark.asyncio
    async def test_remote_protocol_error_exhausted_retries_prefixes_error(self):
        """All 3 attempts fail with RemoteProtocolError; error message gets retry prefix."""
        provider = _make_provider()
        request = _make_request()

        with (
            patch.object(
                provider._client.chat.completions,
                "create",
                new_callable=AsyncMock,
                side_effect=[
                    _make_remote_protocol_error("drop 1"),
                    _make_remote_protocol_error("drop 2"),
                    _make_remote_protocol_error("drop 3"),
                ],
            ),
            patch.object(
                provider._global_rate_limiter,
                "wait_if_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("providers.openai_compat.asyncio.sleep", new_callable=AsyncMock),
        ):
            events = await _collect_stream(provider, request)

        event_text = "".join(events)
        # After 2 retries exhausted (attempt index 2), the prefix should show
        assert "fcc-server 2 retry" in event_text
        assert "message_stop" in event_text

    @pytest.mark.asyncio
    async def test_read_error_is_also_retryable(self):
        """httpx.ReadError triggers the same retry logic."""
        provider = _make_provider()
        request = _make_request()

        chunk_ok = _make_chunk(content="Read retry ok", finish_reason="stop")
        stream_ok = AsyncStreamMock([chunk_ok])

        with (
            patch.object(
                provider._client.chat.completions,
                "create",
                new_callable=AsyncMock,
                side_effect=[
                    _make_read_error("read failed"),
                    stream_ok,
                ],
            ),
            patch.object(
                provider._global_rate_limiter,
                "wait_if_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("providers.openai_compat.asyncio.sleep", new_callable=AsyncMock),
        ):
            events = await _collect_stream(provider, request)

        event_text = "".join(events)
        assert "Read retry ok" in event_text

    @pytest.mark.asyncio
    async def test_non_retryable_error_has_no_retry_prefix(self):
        """Non-transport errors (e.g. RuntimeError) are not retried and have no prefix."""
        provider = _make_provider()
        request = _make_request()

        with (
            patch.object(
                provider._client.chat.completions,
                "create",
                new_callable=AsyncMock,
                side_effect=RuntimeError("Non-transport error"),
            ),
            patch.object(
                provider._global_rate_limiter,
                "wait_if_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            events = await _collect_stream(provider, request)

        event_text = "".join(events)
        assert "fcc-server" not in event_text
        assert "Non-transport error" in event_text

    @pytest.mark.asyncio
    async def test_mid_stream_remote_protocol_error_retries(self):
        """RemoteProtocolError after partial content triggers retry; retry succeeds."""
        provider = _make_provider()
        request = _make_request()

        # First attempt: partial content then drop
        chunk_partial = _make_chunk(content="Partial ")
        stream_fail = AsyncStreamMock([chunk_partial], error=_make_remote_protocol_error())

        # Second attempt: full response
        chunk_ok = _make_chunk(content="Complete response", finish_reason="stop")
        stream_ok = AsyncStreamMock([chunk_ok])

        with (
            patch.object(
                provider._client.chat.completions,
                "create",
                new_callable=AsyncMock,
                side_effect=[stream_fail, stream_ok],
            ),
            patch.object(
                provider._global_rate_limiter,
                "wait_if_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("providers.openai_compat.asyncio.sleep", new_callable=AsyncMock),
        ):
            events = await _collect_stream(provider, request)

        event_text = "".join(events)
        # The retry's content should appear
        assert "Complete response" in event_text
        assert "message_stop" in event_text

    @pytest.mark.asyncio
    async def test_exhausted_retry_after_partial_content_prefixes_error(self):
        """After partial content + 2 retries exhausted, error has fcc-server prefix."""
        provider = _make_provider()
        request = _make_request()

        chunk_partial = _make_chunk(content="Partial ")
        stream_fail = AsyncStreamMock([chunk_partial], error=_make_remote_protocol_error())

        with (
            patch.object(
                provider._client.chat.completions,
                "create",
                new_callable=AsyncMock,
                side_effect=[
                    stream_fail,  # attempt 0: partial + drop
                    _make_remote_protocol_error("drop 1"),  # attempt 1: immediate drop
                    _make_remote_protocol_error("drop 2"),  # attempt 2: immediate drop
                ],
            ),
            patch.object(
                provider._global_rate_limiter,
                "wait_if_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
            patch("providers.openai_compat.asyncio.sleep", new_callable=AsyncMock),
        ):
            events = await _collect_stream(provider, request)

        event_text = "".join(events)
        assert "fcc-server 2 retry" in event_text
        assert "message_stop" in event_text

    @pytest.mark.asyncio
    async def test_single_remote_protocol_error_no_retry_prefix(self):
        """If only one attempt (index 0) fails with non-retryable or attempt==0 on first failure (shouldn't happen with max_retries=2), no prefix."""
        # This test verifies that the retry prefix only appears when attempt > 0
        # A single non-transport error at attempt 0 should have no prefix
        provider = _make_provider()
        request = _make_request()

        with (
            patch.object(
                provider._client.chat.completions,
                "create",
                new_callable=AsyncMock,
                side_effect=httpx.ReadTimeout("timed out"),
            ),
            patch.object(
                provider._global_rate_limiter,
                "wait_if_blocked",
                new_callable=AsyncMock,
                return_value=False,
            ),
        ):
            events = await _collect_stream(provider, request)

        event_text = "".join(events)
        # ReadTimeout is not a retryable transport error, so no retry, no prefix
        assert "fcc-server" not in event_text
        assert "timed out" in event_text
