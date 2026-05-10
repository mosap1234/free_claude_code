"""Tests for the transient-error classifier."""

from __future__ import annotations

import httpx
import openai
import pytest

from providers.transient_errors import classify


def _http_status_error(status: int, body: str = "") -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://example.test/")
    response = httpx.Response(status, request=request, text=body)
    return httpx.HTTPStatusError(
        f"HTTP {status}", request=request, response=response
    )


@pytest.mark.parametrize("status", [502, 503, 504, 520, 522, 524, 408, 429])
def test_retryable_5xx_and_throttling_codes(status: int):
    cls = classify(_http_status_error(status))
    assert cls.is_transient
    assert cls.cause == f"http_{status}"


@pytest.mark.parametrize("status", [400, 401, 403, 404, 405, 410, 422])
def test_non_retryable_client_errors(status: int):
    """Generic client errors should NOT retry (404 cold-start tested separately)."""
    cls = classify(_http_status_error(status))
    assert not cls.is_transient


def test_404_with_nim_function_marker_is_transient():
    body = (
        '{"status":404,"title":"Not Found",'
        '"detail":"Function 84bf12ff-edbd-4435-baea-0fa6a7453d2e: '
        'Not found for account ABC"}'
    )
    cls = classify(_http_status_error(404, body))
    assert cls.is_transient
    assert cls.cause == "nim_cold_start"


def test_404_without_nim_marker_is_not_transient():
    cls = classify(_http_status_error(404, '{"detail":"model not found"}'))
    assert not cls.is_transient


def test_httpx_connection_errors_are_transient():
    request = httpx.Request("POST", "https://example.test/")
    for exc, expected_cause in (
        (httpx.ConnectError("dns failed", request=request), "httpx_connect"),
        (httpx.ConnectTimeout("tls", request=request), "httpx_connect_timeout"),
        (httpx.ReadTimeout("slow", request=request), "httpx_read_timeout"),
        (httpx.WriteError("send failed", request=request), "httpx_write_error"),
        (
            httpx.RemoteProtocolError("dropped", request=request),
            "httpx_remote_protocol",
        ),
        (httpx.PoolTimeout("pool", request=request), "httpx_pool_timeout"),
    ):
        cls = classify(exc)
        assert cls.is_transient, exc
        assert cls.cause == expected_cause


def test_openai_transport_errors_are_transient():
    # APIConnectionError/APITimeoutError require constructor args; build minimal.
    request = httpx.Request("POST", "https://example.test/")
    cls = classify(openai.APIConnectionError(request=request))
    assert cls.is_transient
    assert cls.cause == "openai_connect"

    cls = classify(openai.APITimeoutError(request=request))
    assert cls.is_transient
    assert cls.cause == "openai_timeout"


def test_unknown_exception_is_not_transient():
    cls = classify(ValueError("unrelated"))
    assert not cls.is_transient
    assert cls.cause == "ValueError"


def test_env_override_changes_retryable_status_codes(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NIM_RETRY_ON_5XX", "500,599")
    # 502 is no longer retryable.
    cls = classify(_http_status_error(502))
    assert not cls.is_transient
    # 500 now is.
    cls = classify(_http_status_error(500))
    assert cls.is_transient


def test_invalid_env_override_falls_back_to_defaults(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("NIM_RETRY_ON_5XX", "garbage,abc")
    cls = classify(_http_status_error(502))
    assert cls.is_transient  # defaults still apply
