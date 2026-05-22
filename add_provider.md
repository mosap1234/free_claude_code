1. go to the `config/provider_catalog.py`
and add the provider base url

```python
FIREWORKS_DEFAULT_BASE = "https://api.fireworks.ai/inference/v1"
```

1. Add the describtion of the provider in the same file (`config/provider_catalog.py`) to the `PROVIDER_CATALOG` dict

```python
"fireworks": ProviderDescriptor(
        provider_id="fireworks",
        transport_type="openai_chat",
        credential_env="FIREWORKS_API_KEY",
        credential_url="https://fireworks.ai/account/api-keys",
        credential_attr="fireworks_api_key",
        default_base_url=FIREWORKS_DEFAULT_BASE,
        proxy_attr="fireworks_proxy",
        capabilities=("chat", "streaming", "tools", "thinking", "rate_limit"),
    ),
```

1. In the `config/settings.py` add the api key setting

```python
   # ==================== Fireworks AI Config ====================
    fireworks_api_key: str = Field(default="", validation_alias="FIREWORKS_API_KEY")
    # ==================== Per-Provider Proxy ====================
   fireworks_proxy: str = Field(default="", validation_alias="FIREWORKS_PROXY")
```

1. Add a module for the new provider in the /providers dir

```python
"""Fireworks AI provider exports."""

from .client import FIREWORKS_BASE_URL, FireworksProvider

__all__ = ["FIREWORKS_BASE_URL", "FireworksProvider"]

```

```python
# providers/fireworks/client.py
"""Fireworks AI provider implementation."""

from typing import Any

from providers.base import ProviderConfig
from providers.openai_compat import OpenAIChatTransport

from .request import build_request_body

FIREWORKS_BASE_URL = "https://api.fireworks.ai/inference/v1"


class FireworksProvider(OpenAIChatTransport):
    """Fireworks AI provider using OpenAI-compatible chat completions."""

    def __init__(self, config: ProviderConfig):
        super().__init__(
            config,
            provider_name="FIREWORKS",
            base_url=config.base_url or FIREWORKS_BASE_URL,
            api_key=config.api_key,
        )

    def _build_request_body(
        self, request: Any, thinking_enabled: bool | None = None
    ) -> dict:
        """Build request body for Fireworks AI."""
        if thinking_enabled is None:
            thinking_enabled = self._is_thinking_enabled(request)
        return build_request_body(
            request,
            thinking_enabled=thinking_enabled,
        )
```

```python
# providers/fireworks/request.py

"""Request builder for Fireworks AI provider."""

from typing import Any

from loguru import logger

from core.anthropic import ReasoningReplayMode, build_base_request_body
from core.anthropic.conversion import OpenAIConversionError
from providers.exceptions import InvalidRequestError


def build_request_body(request_data: Any, *, thinking_enabled: bool) -> dict:
    """Build OpenAI-format request body from Anthropic request for Fireworks AI."""
    logger.debug(
        "FIREWORKS_REQUEST: conversion start model={} msgs={}",
        getattr(request_data, "model", "?"),
        len(getattr(request_data, "messages", [])),
    )
    try:
        body = build_base_request_body(
            request_data,
            reasoning_replay=ReasoningReplayMode.REASONING_CONTENT,
        )
    except OpenAIConversionError as exc:
        raise InvalidRequestError(str(exc)) from exc

    extra_body: dict[str, Any] = {}
    request_extra = getattr(request_data, "extra_body", None)
    if request_extra:
        extra_body.update(request_extra)

    if extra_body:
        body["extra_body"] = extra_body

    logger.debug(
        "FIREWORKS_REQUEST: conversion done model={} msgs={} tools={}",
        body.get("model"),
        len(body.get("messages", [])),
        len(body.get("tools", [])),
    )
    return body
```

1. Don't forget to add it as a registry

```python
# providers/registry.py
def _create_fireworks(config: ProviderConfig, _settings: Settings) -> BaseProvider:
    from providers.fireworks import FireworksProvider

    return FireworksProvider(config)

## In the PROVIDER_FACTORIES

   "fireworks": _create_fireworks,
```

1. Don't forget to add it to the admin page

```python
# api/admin_config.py
    ConfigFieldSpec(
        "BASETEN_API_KEY",
        "BASETEN API Key",
        "providers",
        "secret",
        settings_attr="BASETEN_API_KEY",
        secret=True,
        description="Baseten API key for custom-hosted OpenAI-compatible endpoints. Base URL is configured separately.",
    ),

```

1. Last but not least

You should update the `try_claude/.github/workflows/claude.yml` and add to the env in `Run translation server`
