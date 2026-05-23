"""Golden HTTP bodies for ingress-domain errors (resolver + gateway auth)."""

from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.app import create_app
from api.dependencies import get_settings
from api.ingress_errors import (
    GatewayInvalidProxyApiKey,
    GatewayMissingProxyApiKey,
    ProviderResolutionAuthFailure,
)
from api.ingress_handlers import register_ingress_exception_handlers
from config.settings import Settings


def _minimal_ingress_app() -> FastAPI:
    app = FastAPI()
    register_ingress_exception_handlers(app)

    @app.get("/resolver")
    async def _resolver() -> None:
        raise ProviderResolutionAuthFailure("credential resolution failed")

    @app.get("/gateway-missing")
    async def _gateway_missing() -> None:
        raise GatewayMissingProxyApiKey()

    @app.get("/gateway-invalid")
    async def _gateway_invalid() -> None:
        raise GatewayInvalidProxyApiKey()

    return app


def test_ingress_handlers_emit_fastapi_detail_json() -> None:
    app = _minimal_ingress_app()
    with TestClient(app) as client:
        r = client.get("/resolver")
        assert r.status_code == 503
        assert r.json() == {"detail": "credential resolution failed"}

        r = client.get("/gateway-missing")
        assert r.status_code == 401
        assert r.json() == {"detail": "Missing API key"}

        r = client.get("/gateway-invalid")
        assert r.status_code == 401
        assert r.json() == {"detail": "Invalid API key"}


def test_create_message_resolver_auth_failure_detail_shape() -> None:
    """ProviderResolutionFailure from resolve_provider yields 503 ``{"detail": ...}``."""

    import api.dependencies as deps

    app = create_app()
    payload = {
        "model": "claude-3-sonnet",
        "max_tokens": 1,
        "messages": [{"role": "user", "content": "hello"}],
    }

    with (
        TestClient(app) as client,
        patch.object(
            deps,
            "resolve_provider",
            side_effect=ProviderResolutionAuthFailure(
                "NVIDIA_NIM_API_KEY is not set. Add it."
            ),
        ),
    ):
        resp = client.post("/v1/messages", json=payload)

    assert resp.status_code == 503
    assert resp.json() == {"detail": "NVIDIA_NIM_API_KEY is not set. Add it."}


def test_gateway_api_key_detail_shapes_on_count_tokens() -> None:
    app = create_app()
    settings = Settings()
    settings.anthropic_auth_token = "s3cr3t"
    app.dependency_overrides[get_settings] = lambda: settings

    payload = {
        "model": "claude-3-sonnet",
        "messages": [{"role": "user", "content": "hello"}],
    }

    with (
        TestClient(app) as client,
        patch("api.routes.get_token_count", return_value=1),
    ):
        missing = client.post("/v1/messages/count_tokens", json=payload)
        assert missing.status_code == 401
        assert missing.json() == {"detail": "Missing API key"}

        bad = client.post(
            "/v1/messages/count_tokens",
            json=payload,
            headers={"X-API-Key": "wrong"},
        )
        assert bad.status_code == 401
        assert bad.json() == {"detail": "Invalid API key"}

    app.dependency_overrides.clear()
