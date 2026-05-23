"""Field coercion and validation implementations for ``config.settings.Settings``.

Call sites stay as :class:`~pydantic.field_validator` / :class:`~pydantic.model_validator`
delegates on the Settings class body.
"""

from __future__ import annotations

from typing import Any

from .provider_catalog import SUPPORTED_PROVIDER_IDS


def parse_empty_str_optional(v: Any) -> Any:
    if v == "":
        return None
    return v


def reset_empty_log_cap_optional(v: Any) -> Any:
    if v == "" or v is None:
        return None
    return v


def validate_whisper_device_value(v: str) -> str:
    if v not in ("cpu", "cuda", "nvidia_nim"):
        raise ValueError(
            f"whisper_device must be 'cpu', 'cuda', or 'nvidia_nim', got {v!r}"
        )
    return v


def validate_messaging_platform_value(v: str) -> str:
    if v not in ("telegram", "discord", "none"):
        raise ValueError(
            f"messaging_platform must be 'telegram', 'discord', or 'none', got {v!r}"
        )
    return v


def validate_positive_messaging_rate_limit(v: int) -> int:
    if v <= 0:
        raise ValueError("messaging_rate_limit must be > 0")
    return v


def validate_positive_messaging_rate_window(v: float) -> float:
    if v <= 0:
        raise ValueError("messaging_rate_window must be > 0")
    return float(v)


def validate_ollama_base_url_value(v: str) -> str:
    if v.rstrip("/").endswith("/v1"):
        raise ValueError(
            "OLLAMA_BASE_URL must be the Ollama root URL for native Anthropic "
            "messages, e.g. http://localhost:11434 (without /v1)."
        )
    return v


def validate_gateway_model_prefixed(v: str | None) -> str | None:
    if v is None:
        return None
    if "/" not in v:
        raise ValueError(
            "Model must be prefixed with provider type. "
            f"Valid providers: {', '.join(SUPPORTED_PROVIDER_IDS)}. "
            "Format: provider_type/model/name"
        )
    provider = v.split("/", 1)[0]
    if provider not in SUPPORTED_PROVIDER_IDS:
        supported = ", ".join(f"'{p}'" for p in SUPPORTED_PROVIDER_IDS)
        raise ValueError(f"Invalid provider: '{provider}'. Supported: {supported}")
    return v
