"""Tests for :mod:`providers.native_messages_support` exports."""

from providers.native_messages_support import oauth_bearer_model_list_headers


def test_oauth_bearer_model_list_headers_bearer_token() -> None:
    """GET ``/models`` helpers share Bearer formatting across transports."""

    assert oauth_bearer_model_list_headers("k") == {"Authorization": "Bearer k"}
