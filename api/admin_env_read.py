"""Read paths, dotenv ingestion, and admin UI config snapshot helpers."""

import os
from collections.abc import Iterable, Mapping
from io import StringIO
from pathlib import Path
from typing import Any

from dotenv import dotenv_values

from config.paths import managed_env_path
from config.provider_catalog import PROVIDER_CATALOG

from .admin_env_shared import display_value, is_locked_source
from .admin_manifest import (
    FIELD_BY_KEY,
    FIELDS,
    SECTIONS,
    ConfigFieldSpec,
    SourceType,
)


def repo_env_path() -> Path:
    """Return the repo-local env path."""
    return Path(".env")


def explicit_env_path() -> Path | None:
    """Return the explicit FCC_ENV_FILE path, when configured."""
    if explicit := os.environ.get("FCC_ENV_FILE"):
        return Path(explicit)
    return None


def configured_env_files() -> tuple[tuple[SourceType, Path], ...]:
    """Return dotenv files in low-to-high precedence order."""
    files: list[tuple[SourceType, Path]] = [
        ("repo_env", repo_env_path()),
        ("managed_env", managed_env_path()),
    ]
    if explicit := explicit_env_path():
        files.append(("explicit_env_file", explicit))
    return tuple(files)


def _template_text() -> str:
    import importlib.resources

    packaged = importlib.resources.files("cli").joinpath("env.example")
    if packaged.is_file():
        return packaged.read_text("utf-8")

    source_template = Path(__file__).resolve().parents[1] / ".env.example"
    if source_template.is_file():
        return source_template.read_text(encoding="utf-8")

    return ""


def _dotenv_values_from_text(text: str) -> dict[str, str]:
    values = dotenv_values(stream=StringIO(text))
    return {key: "" if value is None else value for key, value in values.items()}


def template_values() -> dict[str, str]:
    """Return .env.example values plus manifest defaults for newer fields."""
    values = _dotenv_values_from_text(_template_text())
    for field in FIELDS:
        values.setdefault(field.key, field.default)
    return values


def _dotenv_values_from_file(path: Path) -> dict[str, str]:
    if not path.is_file():
        return {}
    values = dotenv_values(path)
    return {key: "" if value is None else value for key, value in values.items()}


def load_value_state() -> dict[str, dict[str, Any]]:
    values = template_values()
    sources: dict[str, SourceType] = {
        key: "template" if key in values else "default" for key in FIELD_BY_KEY
    }

    for source, path in configured_env_files():
        file_values = _dotenv_values_from_file(path)
        for key, value in file_values.items():
            if key in FIELD_BY_KEY:
                values[key] = value
                sources[key] = source

    for key in FIELD_BY_KEY:
        if key in os.environ:
            values[key] = os.environ[key]
            sources[key] = "process"

    return {
        key: {
            "value": values.get(key, ""),
            "source": sources.get(key, "default"),
        }
        for key in FIELD_BY_KEY
    }


def load_config_response() -> dict[str, Any]:
    """Return manifest and current config values for the admin UI."""
    state = load_value_state()
    fields: list[dict[str, Any]] = []
    for field in FIELDS:
        entry = state[field.key]
        source = entry["source"]
        raw_value = entry["value"]
        fields.append(
            {
                "key": field.key,
                "label": field.label,
                "section": field.section_id,
                "type": field.field_type,
                "value": display_value(field, raw_value),
                "configured": bool(str(raw_value).strip()),
                "source": source,
                "locked": is_locked_source(source),
                "secret": field.secret,
                "advanced": field.advanced,
                "restart_required": field.restart_required,
                "session_sensitive": field.session_sensitive,
                "options": list(field.options),
                "description": field.description,
            }
        )

    return {
        "sections": [
            {
                "id": section.section_id,
                "label": section.label,
                "description": section.description,
                "advanced": section.advanced,
            }
            for section in SECTIONS
        ],
        "fields": fields,
        "paths": {
            "managed": str(managed_env_path()),
            "repo": str(repo_env_path()),
            "explicit": str(explicit_env_path()) if explicit_env_path() else None,
        },
        "provider_status": provider_config_status(state),
    }


def _value_for_settings_attr(
    state: Mapping[str, Mapping[str, Any]], settings_attr: str
) -> str:
    for field in FIELDS:
        if field.settings_attr == settings_attr:
            return str(state.get(field.key, {}).get("value", field.default))
    return ""


def provider_config_status(
    state: Mapping[str, Mapping[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    """Return provider configuration status without making network calls."""
    state = state or load_value_state()
    statuses: list[dict[str, Any]] = []
    for provider_id, descriptor in PROVIDER_CATALOG.items():
        if descriptor.credential_env is None:
            base_url = ""
            if descriptor.base_url_attr is not None:
                base_url = _value_for_settings_attr(state, descriptor.base_url_attr)
            statuses.append(
                {
                    "provider_id": provider_id,
                    "kind": "local",
                    "status": "missing_url" if not base_url.strip() else "unknown",
                    "label": "Missing URL" if not base_url.strip() else "Not checked",
                    "base_url": base_url or descriptor.default_base_url or "",
                }
            )
            continue

        value = str(state.get(descriptor.credential_env, {}).get("value", ""))
        configured = bool(value.strip())
        statuses.append(
            {
                "provider_id": provider_id,
                "kind": "remote",
                "status": "configured" if configured else "missing_key",
                "label": "Configured" if configured else "Missing key",
                "credential_env": descriptor.credential_env,
            }
        )
    return statuses


def env_keys() -> frozenset[str]:
    """Return env keys owned by the admin manifest."""
    return frozenset(field.key for field in FIELDS)


def fields_with_attrs() -> Iterable[ConfigFieldSpec]:
    """Yield fields that validate through Settings."""
    return (field for field in FIELDS if field.settings_attr is not None)
