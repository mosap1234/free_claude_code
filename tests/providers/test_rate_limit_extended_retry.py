"""Tests for the extended retry behaviour on transient transport errors."""

from __future__ import annotations

import httpx
import openai
import pytest

from providers.rate_limit import GlobalRateLimiter


def _http_status_error(status: int, body: str = "") -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://example.test/")
    response = httpx.Response(status, request=request, text=body)
    return httpx.HTTPStatusError(
        f"HTTP {status}", request=request, response=response
    )


@pytest.fixture
def fast_limiter() -> GlobalRateLimiter:
    """Limiter with negligible backoff so tests run quickly."""
    return GlobalRateLimiter(rate_limit=100, rate_window=60.0, max_concurrency=5)


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [502, 503, 504, 520, 522, 524, 408])
async def test_retries_transient_5xx(
    fast_limiter: GlobalRateLimiter, status: int
):
    calls = 0

    async def fail_then_ok():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise _http_status_error(status, body="upstream broken")
        return "ok"

    result = await fast_limiter.execute_with_retry(
        fail_then_ok, max_retries=2, base_delay=0.01, max_delay=0.05, jitter=0
    )
    assert result == "ok"
    assert calls == 2


@pytest.mark.asyncio
async def test_retries_nim_cold_start_404(fast_limiter: GlobalRateLimiter):
    body = (
        '{"status":404,"title":"Not Found",'
        '"detail":"Function abc: Not found for account XYZ"}'
    )
    calls = 0

    async def fail_then_ok():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise _http_status_error(404, body=body)
        return "warm"

    result = await fast_limiter.execute_with_retry(
        fail_then_ok, max_retries=2, base_delay=0.01, max_delay=0.05, jitter=0
    )
    assert result == "warm"
    assert calls == 2


@pytest.mark.asyncio
async def test_does_not_retry_genuine_404(fast_limiter: GlobalRateLimiter):
    """A non-NIM 404 (e.g. unknown model) must NOT retry."""
    calls = 0

    async def always_404():
        nonlocal calls
        calls += 1
        raise _http_status_error(404, body='{"detail":"model not found"}')

    with pytest.raises(httpx.HTTPStatusError):
        await fast_limiter.execute_with_retry(
            always_404, max_retries=3, base_delay=0.01, max_delay=0.05, jitter=0
        )
    assert calls == 1


@pytest.mark.asyncio
async def test_retries_httpx_connection_errors(fast_limiter: GlobalRateLimiter):
    request = httpx.Request("POST", "https://example.test/")
    calls = 0

    async def flaky():
        nonlocal calls
        calls += 1
        if calls < 3:
            raise httpx.ConnectError("dns flake", request=request)
        return "ok"

    result = await fast_limiter.execute_with_retry(
        flaky, max_retries=3, base_delay=0.01, max_delay=0.05, jitter=0
    )
    assert result == "ok"
    assert calls == 3


@pytest.mark.asyncio
async def test_retries_remote_protocol_error(fast_limiter: GlobalRateLimiter):
    request = httpx.Request("POST", "https://example.test/")
    calls = 0

    async def flaky():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise httpx.RemoteProtocolError("connection dropped", request=request)
        return "ok"

    result = await fast_limiter.execute_with_retry(
        flaky, max_retries=2, base_delay=0.01, max_delay=0.05, jitter=0
    )
    assert result == "ok"
    assert calls == 2


@pytest.mark.asyncio
async def test_retries_openai_internal_server_error(fast_limiter: GlobalRateLimiter):
    request = httpx.Request("POST", "https://example.test/")
    response = httpx.Response(500, request=request, text="oops")
    calls = 0

    async def flaky():
        nonlocal calls
        calls += 1
        if calls == 1:
            raise openai.InternalServerError(
                "internal", response=response, body=None
            )
        return "ok"

    result = await fast_limiter.execute_with_retry(
        flaky, max_retries=2, base_delay=0.01, max_delay=0.05, jitter=0
    )
    assert result == "ok"
    assert calls == 2


@pytest.mark.asyncio
async def test_exhausts_retries_and_raises_last(fast_limiter: GlobalRateLimiter):
    request = httpx.Request("POST", "https://example.test/")
    calls = 0

    async def always_fails():
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("dead", request=request)

    with pytest.raises(httpx.ConnectError):
        await fast_limiter.execute_with_retry(
            always_fails, max_retries=2, base_delay=0.01, max_delay=0.05, jitter=0
        )
    assert calls == 3  # initial + 2 retries


@pytest.mark.asyncio
async def test_does_not_retry_non_transient(fast_limiter: GlobalRateLimiter):
    """A 401 is non-transient; should propagate after one attempt."""
    calls = 0

    async def auth_fail():
        nonlocal calls
        calls += 1
        raise _http_status_error(401, body="unauthorised")

    with pytest.raises(httpx.HTTPStatusError):
        await fast_limiter.execute_with_retry(
            auth_fail, max_retries=3, base_delay=0.01, max_delay=0.05, jitter=0
        )
    assert calls == 1


@pytest.mark.asyncio
async def test_env_overrides_drive_retry_count(
    fast_limiter: GlobalRateLimiter, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setenv("NIM_RETRY_MAX_ATTEMPTS", "2")
    monkeypatch.setenv("NIM_RETRY_BASE_DELAY_S", "0.01")
    monkeypatch.setenv("NIM_RETRY_MAX_DELAY_S", "0.05")
    monkeypatch.setenv("NIM_RETRY_JITTER_S", "0")
    request = httpx.Request("POST", "https://example.test/")
    calls = 0

    async def fails():
        nonlocal calls
        calls += 1
        raise httpx.ConnectError("nope", request=request)

    with pytest.raises(httpx.ConnectError):
        # Pass None to use env defaults.
        await fast_limiter.execute_with_retry(fails)
    assert calls == 2  # NIM_RETRY_MAX_ATTEMPTS=2 → 1 retry → 2 total
