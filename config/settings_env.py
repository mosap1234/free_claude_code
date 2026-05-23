"""Env file path helpers and migration guards shared by ``config.settings.Settings``."""

from __future__ import annotations

import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

from .paths import managed_env_path


def env_files_list() -> tuple[Path, ...]:
    """Return env file paths in priority order (later overrides earlier)."""
    files: list[Path] = [
        Path(".env"),
        managed_env_path(),
    ]
    if explicit := os.environ.get("FCC_ENV_FILE"):
        files.append(Path(explicit))
    return tuple(files)


def configured_env_paths(model_config: Mapping[str, Any]) -> tuple[Path, ...]:
    """Return the currently configured env files for Settings."""
    configured = model_config.get("env_file")
    if configured is None:
        return ()
    if isinstance(configured, (str, Path)):
        return (Path(configured),)
    return tuple(Path(item) for item in configured)


def dotenv_contains_key(path: Path, key: str) -> bool:
    """Check whether a dotenv-style file defines the given key."""
    return dotenv_value(path, key) is not None


def dotenv_value(path: Path, key: str) -> str | None:
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


def dotenv_last_value_for_key(model_config: Mapping[str, Any], key: str) -> str | None:
    """Return the last configured dotenv value that explicitly defines a key."""
    configured_value: str | None = None
    for env_file in configured_env_paths(model_config):
        value = dotenv_value(env_file, key)
        if value is not None:
            configured_value = value
    return configured_value


def removed_env_var_migration_error(model_config: Mapping[str, Any]) -> str | None:
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

        for env_file in configured_env_paths(model_config):
            if dotenv_contains_key(env_file, removed_key):
                return (
                    f"{removed_key} has been removed in this release. "
                    f"Rename it to {replacement}. Found in {env_file}."
                )

    return None
