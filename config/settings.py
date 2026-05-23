"""Centralized configuration using Pydantic Settings."""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from dotenv import dotenv_values
from pydantic import computed_field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from .admin_optimization_settings import AdminOptimizationSettings
from .bot_settings import BotSettings
from .messaging_settings import MessagingSettings
from .model_routing_settings import ModelRoutingSettings
from .observability_settings import ObservabilitySettings
from .paths import default_claude_workspace_path, managed_env_path
from .provider_ids import SUPPORTED_PROVIDER_IDS
from .server_runtime_settings import ProviderThroughputSettings, ServerRuntimeSettings
from .settings_credentials import ProviderCredentialsMixin
from .settings_http import HttpAndThroughputMixin
from .settings_local_providers import LocalProviderEndpointsMixin
from .settings_messaging import MessagingAndBotsMixin
from .settings_model_routing import ModelRoutingMixin
from .settings_nim_chat import NimChatMixin
from .settings_observability import ObservabilityMixin
from .settings_optimizations import RequestOptimizationsMixin
from .settings_proxies import ProviderProxyMixin
from .settings_server import ServerBindMixin
from .settings_voice import VoiceNoteMixin
from .settings_web_tools import WebServerToolsMixin
from .web_fetch_settings import WebFetchSettings, normalize_web_fetch_allowed_schemes


@dataclass(frozen=True, slots=True)
class ConfiguredChatModelRef:
    """A unique configured chat model reference and the env keys that set it."""

    model_ref: str
    provider_id: str
    model_id: str
    sources: tuple[str, ...]


def _env_files() -> tuple[Path, ...]:
    """Return env file paths in priority order (later overrides earlier)."""
    files: list[Path] = [
        Path(".env"),
        managed_env_path(),
    ]
    if explicit := os.environ.get("FCC_ENV_FILE"):
        files.append(Path(explicit))
    return tuple(files)


def _configured_env_files(model_config: Mapping[str, Any]) -> tuple[Path, ...]:
    """Return the currently configured env files for Settings."""
    configured = model_config.get("env_file")
    if configured is None:
        return ()
    if isinstance(configured, (str, Path)):
        return (Path(configured),)
    return tuple(Path(item) for item in configured)


def _env_file_contains_key(path: Path, key: str) -> bool:
    """Check whether a dotenv-style file defines the given key."""
    return _env_file_value(path, key) is not None


def _env_file_value(path: Path, key: str) -> str | None:
    """Return a dotenv value when the file explicitly defines the key."""
    if not path.is_file():
        return None

    try:
        values = dotenv_values(path)
    except OSError:
        return None

    if key not in values:
        return None
    value = values[key]
    return "" if value is None else value


def _env_file_override(model_config: Mapping[str, Any], key: str) -> str | None:
    """Return the last configured dotenv value that explicitly defines a key."""
    configured_value: str | None = None
    for env_file in _configured_env_files(model_config):
        value = _env_file_value(env_file, key)
        if value is not None:
            configured_value = value
    return configured_value


def _removed_env_var_message(model_config: Mapping[str, Any]) -> str | None:
    """Return a migration error for removed env vars, if present."""
    removed_keys = ("NIM_ENABLE_THINKING", "ENABLE_THINKING")
    replacement = (
        "ENABLE_MODEL_THINKING, ENABLE_OPUS_THINKING, "
        "ENABLE_SONNET_THINKING, or ENABLE_HAIKU_THINKING"
    )

    for removed_key in removed_keys:
        if removed_key in os.environ:
            return (
                f"{removed_key} has been removed in this release. "
                f"Rename it to {replacement}."
            )

        for env_file in _configured_env_files(model_config):
            if _env_file_contains_key(env_file, removed_key):
                return (
                    f"{removed_key} has been removed in this release. "
                    f"Rename it to {replacement}. Found in {env_file}."
                )

    return None


class Settings(
    ProviderCredentialsMixin,
    LocalProviderEndpointsMixin,
    ProviderProxyMixin,
    ModelRoutingMixin,
    HttpAndThroughputMixin,
    RequestOptimizationsMixin,
    WebServerToolsMixin,
    ObservabilityMixin,
    NimChatMixin,
    VoiceNoteMixin,
    MessagingAndBotsMixin,
    ServerBindMixin,
    BaseSettings,
):
    """Application settings loaded from environment variables."""

    @model_validator(mode="before")
    @classmethod
    def reject_removed_env_vars(cls, data: Any) -> Any:
        """Fail fast when removed environment variables are still configured."""
        if message := _removed_env_var_message(cls.model_config):
            raise ValueError(message)
        return data

    @field_validator(
        "telegram_bot_token",
        "allowed_telegram_user_id",
        "discord_bot_token",
        "allowed_discord_channels",
        "model_opus",
        "model_sonnet",
        "model_haiku",
        "enable_opus_thinking",
        "enable_sonnet_thinking",
        "enable_haiku_thinking",
        mode="before",
    )
    @classmethod
    def parse_optional_str(cls, v: Any) -> Any:
        if v == "":
            return None
        return v

    @field_validator("max_message_log_entries_per_chat", mode="before")
    @classmethod
    def parse_optional_log_cap(cls, v: Any) -> Any:
        if v == "" or v is None:
            return None
        return v

    @property
    def claude_workspace(self) -> str:
        """Return the fixed Claude data workspace path."""

        return str(default_claude_workspace_path())

    @property
    def claude_cli_bin(self) -> str:
        """Return the fixed Claude Code binary name."""

        return "claude"

    @field_validator("whisper_device")
    @classmethod
    def validate_whisper_device(cls, v: str) -> str:
        if v not in ("cpu", "cuda", "nvidia_nim"):
            raise ValueError(
                f"whisper_device must be 'cpu', 'cuda', or 'nvidia_nim', got {v!r}"
            )
        return v

    @field_validator("messaging_platform")
    @classmethod
    def validate_messaging_platform(cls, v: str) -> str:
        if v not in ("telegram", "discord", "none"):
            raise ValueError(
                f"messaging_platform must be 'telegram', 'discord', or 'none', got {v!r}"
            )
        return v

    @field_validator("messaging_rate_limit")
    @classmethod
    def validate_messaging_rate_limit(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("messaging_rate_limit must be > 0")
        return v

    @field_validator("messaging_rate_window")
    @classmethod
    def validate_messaging_rate_window(cls, v: float) -> float:
        if v <= 0:
            raise ValueError("messaging_rate_window must be > 0")
        return float(v)

    @field_validator("web_fetch_allowed_schemes")
    @classmethod
    def validate_web_fetch_allowed_schemes(cls, v: str) -> str:
        return normalize_web_fetch_allowed_schemes(v)

    @field_validator("ollama_base_url")
    @classmethod
    def validate_ollama_base_url(cls, v: str) -> str:
        if v.rstrip("/").endswith("/v1"):
            raise ValueError(
                "OLLAMA_BASE_URL must be the Ollama root URL for native Anthropic "
                "messages, e.g. http://localhost:11434 (without /v1)."
            )
        return v

    @field_validator("model", "model_opus", "model_sonnet", "model_haiku")
    @classmethod
    def validate_model_format(cls, v: str | None) -> str | None:
        if v is None:
            return None
        if "/" not in v:
            raise ValueError(
                f"Model must be prefixed with provider type. "
                f"Valid providers: {', '.join(SUPPORTED_PROVIDER_IDS)}. "
                f"Format: provider_type/model/name"
            )
        provider = v.split("/", 1)[0]
        if provider not in SUPPORTED_PROVIDER_IDS:
            supported = ", ".join(f"'{p}'" for p in SUPPORTED_PROVIDER_IDS)
            raise ValueError(f"Invalid provider: '{provider}'. Supported: {supported}")
        return v

    @model_validator(mode="after")
    def check_nvidia_nim_api_key(self) -> Settings:
        if (
            self.voice_note_enabled
            and self.whisper_device == "nvidia_nim"
            and not self.nvidia_nim_api_key.strip()
        ):
            raise ValueError(
                "NVIDIA_NIM_API_KEY is required when WHISPER_DEVICE is 'nvidia_nim'. "
                "Set it in your .env file."
            )
        return self

    @model_validator(mode="after")
    def prefer_dotenv_anthropic_auth_token(self) -> Settings:
        """Let explicit .env auth config override stale shell/client tokens."""
        dotenv_value = _env_file_override(self.model_config, "ANTHROPIC_AUTH_TOKEN")
        if dotenv_value is not None:
            self.anthropic_auth_token = dotenv_value
        return self

    def uses_process_anthropic_auth_token(self) -> bool:
        """Return whether proxy auth came from process env, not dotenv config."""
        if _env_file_override(self.model_config, "ANTHROPIC_AUTH_TOKEN") is not None:
            return False
        return bool(os.environ.get("ANTHROPIC_AUTH_TOKEN"))

    @property
    def provider_type(self) -> str:
        """Extract provider type from the default model string."""
        return Settings.parse_provider_type(self.model)

    @property
    def model_name(self) -> str:
        """Extract the actual model name from the default model string."""
        return Settings.parse_model_name(self.model)

    def resolve_model(self, claude_model_name: str) -> str:
        """Resolve a Claude model name to the configured provider/model string.

        Classifies the incoming Claude model (opus/sonnet/haiku) and
        returns the model-specific override if configured, otherwise the fallback MODEL.
        """
        name_lower = claude_model_name.lower()
        if "opus" in name_lower and self.model_opus is not None:
            return self.model_opus
        if "haiku" in name_lower and self.model_haiku is not None:
            return self.model_haiku
        if "sonnet" in name_lower and self.model_sonnet is not None:
            return self.model_sonnet
        return self.model

    def configured_chat_model_refs(self) -> tuple[ConfiguredChatModelRef, ...]:
        """Return unique configured chat provider/model refs with source env keys."""
        candidates = (
            ("MODEL", self.model),
            ("MODEL_OPUS", self.model_opus),
            ("MODEL_SONNET", self.model_sonnet),
            ("MODEL_HAIKU", self.model_haiku),
        )
        sources_by_ref: dict[str, list[str]] = {}
        for source, model_ref in candidates:
            if model_ref is None:
                continue
            sources_by_ref.setdefault(model_ref, []).append(source)

        return tuple(
            ConfiguredChatModelRef(
                model_ref=model_ref,
                provider_id=Settings.parse_provider_type(model_ref),
                model_id=Settings.parse_model_name(model_ref),
                sources=tuple(sources),
            )
            for model_ref, sources in sources_by_ref.items()
        )

    def resolve_thinking(self, claude_model_name: str) -> bool:
        """Resolve whether thinking is enabled for an incoming Claude model name."""
        name_lower = claude_model_name.lower()
        if "opus" in name_lower and self.enable_opus_thinking is not None:
            return self.enable_opus_thinking
        if "haiku" in name_lower and self.enable_haiku_thinking is not None:
            return self.enable_haiku_thinking
        if "sonnet" in name_lower and self.enable_sonnet_thinking is not None:
            return self.enable_sonnet_thinking
        return self.enable_model_thinking

    def web_fetch_allowed_scheme_set(self) -> frozenset[str]:
        """Return normalized schemes allowed for web_fetch."""
        return self.web_fetch_bundle.allowed_scheme_set()

    @property
    def web_fetch_bundle(self) -> WebFetchSettings:
        """Grouped web_fetch / web_search guard settings."""
        return WebFetchSettings(
            enable_web_server_tools=self.enable_web_server_tools,
            web_fetch_allowed_schemes=self.web_fetch_allowed_schemes,
            web_fetch_allow_private_networks=self.web_fetch_allow_private_networks,
        )

    @property
    def observability_bundle(self) -> ObservabilitySettings:
        """Bundled verbosity and debug logging flags."""
        return ObservabilitySettings(
            log_raw_api_payloads=self.log_raw_api_payloads,
            log_raw_sse_events=self.log_raw_sse_events,
            log_api_error_tracebacks=self.log_api_error_tracebacks,
            log_raw_messaging_content=self.log_raw_messaging_content,
            log_raw_cli_diagnostics=self.log_raw_cli_diagnostics,
            log_messaging_error_details=self.log_messaging_error_details,
            debug_platform_edits=self.debug_platform_edits,
            debug_subagent_stack=self.debug_subagent_stack,
        )

    @property
    def model_routing_bundle(self) -> ModelRoutingSettings:
        """Model tiers and thinking knobs grouped for dashboards and manifests."""
        return ModelRoutingSettings(
            model=self.model,
            model_opus=self.model_opus,
            model_sonnet=self.model_sonnet,
            model_haiku=self.model_haiku,
            enable_model_thinking=self.enable_model_thinking,
            enable_opus_thinking=self.enable_opus_thinking,
            enable_sonnet_thinking=self.enable_sonnet_thinking,
            enable_haiku_thinking=self.enable_haiku_thinking,
        )

    @property
    def bot_bundle(self) -> BotSettings:
        """Bots, workspace guard rails, and voice-note configuration."""
        return BotSettings(
            telegram_bot_token=self.telegram_bot_token,
            allowed_telegram_user_id=self.allowed_telegram_user_id,
            discord_bot_token=self.discord_bot_token,
            allowed_discord_channels=self.allowed_discord_channels,
            allowed_dir=self.allowed_dir,
            max_message_log_entries_per_chat=self.max_message_log_entries_per_chat,
            voice_note_enabled=self.voice_note_enabled,
            whisper_device=self.whisper_device,
            whisper_model=self.whisper_model,
            hf_token=self.hf_token,
        )

    @property
    def admin_optimization_bundle(self) -> AdminOptimizationSettings:
        """Admin-visible proxy shortcuts unrelated to throughput rate limits."""
        return AdminOptimizationSettings(
            fast_prefix_detection=self.fast_prefix_detection,
            enable_network_probe_mock=self.enable_network_probe_mock,
            enable_title_generation_skip=self.enable_title_generation_skip,
            enable_suggestion_mode_skip=self.enable_suggestion_mode_skip,
            enable_filepath_extraction_mock=self.enable_filepath_extraction_mock,
        )

    @computed_field
    def messaging_bundle(self) -> MessagingSettings:
        """Messaging knobs grouped for injection into optional bot runtime."""
        return MessagingSettings(
            messaging_platform=self.messaging_platform,
            messaging_rate_limit=self.messaging_rate_limit,
            messaging_rate_window=self.messaging_rate_window,
            log_messaging_error_details=self.log_messaging_error_details,
            log_raw_messaging_content=self.log_raw_messaging_content,
        )

    @computed_field
    def server_runtime_bundle(self) -> ServerRuntimeSettings:
        """Primary HTTP bind + auth subset."""
        return ServerRuntimeSettings(
            host=self.host,
            port=self.port,
            anthropic_auth_token=self.anthropic_auth_token,
        )

    @computed_field
    def provider_throughput_bundle(self) -> ProviderThroughputSettings:
        """Values mirrored into each :class:`~providers.base.ProviderConfig` instance."""
        return ProviderThroughputSettings(
            provider_rate_limit=self.provider_rate_limit,
            provider_rate_window=self.provider_rate_window,
            provider_max_concurrency=self.provider_max_concurrency,
        )

    @staticmethod
    def parse_provider_type(model_string: str) -> str:
        """Extract provider type from any 'provider/model' string."""
        return model_string.split("/", 1)[0]

    @staticmethod
    def parse_model_name(model_string: str) -> str:
        """Extract model name from any 'provider/model' string."""
        return model_string.split("/", 1)[1]

    model_config = SettingsConfigDict(
        env_file=_env_files(),
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


def reload_settings() -> Settings:
    """Clear cached settings and return a fresh ``Settings()`` instance."""
    get_settings.cache_clear()
    return get_settings()
