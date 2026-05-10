"""Environment-driven configuration for the agent governor."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


_DEFAULT_WEAK_PATTERNS = (
    "qwen",
    "nemotron",
    "deepseek-chat",
    "deepseek-coder",
    "kimi",
    "moonshot",
    "gpt-oss",
    "glm",
    "mistral",
    "llama",
    "wafer",
    "ring",
    "minimax",
    "gemma",
    "hermes",
    "command",
    "yi-",
)
_DEFAULT_STRONG_PATTERNS = (
    "claude-",
    "gpt-5",
    "gpt-4",
    "o1-",
    "o3-",
    "o4-",
    "grok-",
    "gemini-",
)


def _bool_env(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def _int_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning(
            "Invalid {} value: {!r} — using default {}", name, raw, default
        )
        return default


def _csv_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return tuple(item.strip().lower() for item in raw.split(",") if item.strip())


def _json_env(name: str) -> dict[str, Any]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning(
            "Invalid {} JSON: {} — ignoring overrides", name, exc.msg
        )
        return {}
    if not isinstance(parsed, dict):
        logger.warning(
            "{} must decode to a JSON object — ignoring overrides", name
        )
        return {}
    return parsed


@dataclass(slots=True)
class ModelOverride:
    """Per-model configuration override (subset of GovernorConfig)."""

    enabled: bool | None = None
    tool_cull_enabled: bool | None = None
    tool_cull_max: int | None = None
    max_consecutive_tool_calls: int | None = None
    max_total_tool_calls: int | None = None
    loop_repeat_threshold: int | None = None
    plan_mode: bool | None = None
    termination_hint: bool | None = None


@dataclass(slots=True)
class GovernorConfig:
    """Resolved governor configuration for one request."""

    enabled: bool = True
    tool_cull_enabled: bool = True
    tool_cull_max: int = 25
    max_consecutive_tool_calls: int = 8
    max_total_tool_calls: int = 40
    loop_repeat_threshold: int = 3
    plan_mode_for_weak: bool = True
    termination_hint_for_weak: bool = True
    weak_model_patterns: tuple[str, ...] = field(default_factory=lambda: _DEFAULT_WEAK_PATTERNS)
    strong_model_patterns: tuple[str, ...] = field(default_factory=lambda: _DEFAULT_STRONG_PATTERNS)
    overrides: dict[str, ModelOverride] = field(default_factory=dict)

    def is_strong_model(self, model_id: str) -> bool:
        lowered = model_id.lower()
        return any(pat in lowered for pat in self.strong_model_patterns)

    def is_weak_model(self, model_id: str) -> bool:
        lowered = model_id.lower()
        return any(pat in lowered for pat in self.weak_model_patterns)

    def for_model(self, model_id: str) -> GovernorConfig:
        """Return effective config after applying per-model overrides."""
        override = self.overrides.get(model_id) or self.overrides.get(
            self._best_override_key(model_id)
        )
        if override is None:
            return self
        return GovernorConfig(
            enabled=override.enabled if override.enabled is not None else self.enabled,
            tool_cull_enabled=override.tool_cull_enabled
            if override.tool_cull_enabled is not None
            else self.tool_cull_enabled,
            tool_cull_max=override.tool_cull_max
            if override.tool_cull_max is not None
            else self.tool_cull_max,
            max_consecutive_tool_calls=override.max_consecutive_tool_calls
            if override.max_consecutive_tool_calls is not None
            else self.max_consecutive_tool_calls,
            max_total_tool_calls=override.max_total_tool_calls
            if override.max_total_tool_calls is not None
            else self.max_total_tool_calls,
            loop_repeat_threshold=override.loop_repeat_threshold
            if override.loop_repeat_threshold is not None
            else self.loop_repeat_threshold,
            plan_mode_for_weak=override.plan_mode
            if override.plan_mode is not None
            else self.plan_mode_for_weak,
            termination_hint_for_weak=override.termination_hint
            if override.termination_hint is not None
            else self.termination_hint_for_weak,
            weak_model_patterns=self.weak_model_patterns,
            strong_model_patterns=self.strong_model_patterns,
            overrides=self.overrides,
        )

    def _best_override_key(self, model_id: str) -> str | None:
        """Find the longest configured key that is a substring of model_id."""
        candidates = [k for k in self.overrides if k and k in model_id]
        if not candidates:
            return None
        return max(candidates, key=len)


def load_governor_config() -> GovernorConfig:
    """Build a GovernorConfig from environment variables (process-level)."""
    cfg = GovernorConfig(
        enabled=_bool_env("GOVERNOR_ENABLED", True),
        tool_cull_enabled=_bool_env("GOVERNOR_TOOL_CULL_ENABLED", True),
        tool_cull_max=_int_env("GOVERNOR_TOOL_CULL_MAX", 25),
        max_consecutive_tool_calls=_int_env(
            "GOVERNOR_MAX_CONSECUTIVE_TOOL_CALLS", 8
        ),
        max_total_tool_calls=_int_env("GOVERNOR_MAX_TOTAL_TOOL_CALLS", 40),
        loop_repeat_threshold=_int_env("GOVERNOR_LOOP_REPEAT_THRESHOLD", 3),
        plan_mode_for_weak=_bool_env("GOVERNOR_PLAN_MODE_FOR_WEAK", True),
        termination_hint_for_weak=_bool_env(
            "GOVERNOR_TERMINATION_HINT_FOR_WEAK", True
        ),
        weak_model_patterns=_csv_env(
            "GOVERNOR_WEAK_MODEL_PATTERNS", _DEFAULT_WEAK_PATTERNS
        ),
        strong_model_patterns=_csv_env(
            "GOVERNOR_STRONG_MODEL_PATTERNS", _DEFAULT_STRONG_PATTERNS
        ),
    )
    overrides_raw = _json_env("GOVERNOR_OVERRIDES_JSON")
    overrides: dict[str, ModelOverride] = {}
    for model_id, payload in overrides_raw.items():
        if not isinstance(model_id, str) or not isinstance(payload, dict):
            continue
        overrides[model_id] = ModelOverride(
            enabled=payload.get("enabled"),
            tool_cull_enabled=payload.get("tool_cull_enabled"),
            tool_cull_max=payload.get("tool_cull_max"),
            max_consecutive_tool_calls=payload.get("max_consecutive_tool_calls"),
            max_total_tool_calls=payload.get("max_total_tool_calls"),
            loop_repeat_threshold=payload.get("loop_repeat_threshold"),
            plan_mode=payload.get("plan_mode"),
            termination_hint=payload.get("termination_hint"),
        )
    cfg.overrides = overrides
    return cfg
