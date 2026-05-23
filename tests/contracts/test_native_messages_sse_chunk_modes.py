"""Regression matrix for native Anthropic SSE observable chunk framing (replay doubles)."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from providers.anthropic_messages import AnthropicMessagesTransport
from providers.base import ProviderConfig
from tests.providers.test_anthropic_messages import FakeResponse, MockRequest


class MatrixNativeTransport(AnthropicMessagesTransport):
    """Same shape as native transport doubles in ``test_anthropic_messages``."""

    def __init__(self, config: ProviderConfig):
        super().__init__(
            config,
            provider_name="TEST_NATIVE",
            default_base_url="https://example.test/v1",
        )

    def _request_headers(self) -> dict[str, str]:
        return {"Content-Type": "application/json", "X-Test": "1"}


@pytest.fixture
def matrix_provider_config() -> ProviderConfig:
    return ProviderConfig(
        api_key="test-key",
        base_url="https://custom.test/v1/",
        proxy="socks5://127.0.0.1:9999",
        rate_limit=10,
        rate_window=60,
        http_read_timeout=600.0,
        http_write_timeout=15.0,
        http_connect_timeout=5.0,
    )


@pytest.fixture(autouse=True)
def _mock_rate_limiter_matrix():
    @asynccontextmanager
    async def _slot():
        yield

    with patch("providers.anthropic_messages_transport.GlobalRateLimiter") as mock:
        instance = mock.get_scoped_instance.return_value

        async def _passthrough(fn, *args, **kwargs):
            return await fn(*args, **kwargs)

        instance.execute_with_retry = AsyncMock(side_effect=_passthrough)
        instance.concurrency_slot.side_effect = _slot
        yield instance


@pytest.mark.native_sse_matrix
@pytest.mark.parametrize("native_mode", ["line", "event"])
@pytest.mark.asyncio
async def test_native_messages_stream_survives_observable_chunk_modes(
    matrix_provider_config: ProviderConfig,
    native_mode: str,
) -> None:
    """Both default ``line`` grouping and observable ``event`` framing must stream cleanly."""

    cfg = matrix_provider_config.model_copy(
        update={"native_stream_chunk_mode": native_mode},
    )
    provider = MatrixNativeTransport(cfg)
    req = MockRequest()
    request_obj = httpx.Request("POST", "https://example.test/v1/messages")
    response = FakeResponse(
        lines=[
            "event: message_start",
            'data: {"type":"message_start"}',
            "",
        ]
    )

    with (
        patch.object(provider._client, "build_request", return_value=request_obj),
        patch.object(
            provider._client,
            "send",
            new_callable=AsyncMock,
            return_value=response,
        ),
    ):
        events = [e async for e in provider.stream_response(req)]

    assert events
    joined = "".join(events)
    assert "message_start" in joined
