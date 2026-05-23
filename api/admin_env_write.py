"""Write managed env snapshots, preview rendering, and validation."""

from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from config.paths import managed_env_path
from config.settings import Settings

from .admin_env_read import _dotenv_values_from_file, load_value_state, template_values
from .admin_env_shared import (
    field_input_key,
    format_validation_errors,
    is_locked_source,
    normalize_for_env,
)
from .admin_manifest import (
    FIELD_BY_KEY,
    FIELDS,
    MASKED_SECRET,
    SECTIONS,
    ConfigFieldSpec,
)


def _target_values_with_updates(updates: Mapping[str, Any]) -> dict[str, str]:
    state = load_value_state()
    values = template_values()

    managed_values = _dotenv_values_from_file(managed_env_path())
    if managed_values:
        values.update(
            {key: val for key, val in managed_values.items() if key in values}
        )
    else:
        for key, entry in state.items():
            if entry["source"] in {"repo_env", "template", "default"}:
                values[key] = str(entry["value"])

    for key, value in updates.items():
        field = FIELD_BY_KEY.get(key)
        if field is None:
            continue
        if is_locked_source(state[key]["source"]):
            continue
        if field.secret and value == MASKED_SECRET:
            continue
        values[key] = normalize_for_env(value)

    for field in FIELDS:
        values.setdefault(field.key, field.default)
    return values


def _effective_values_for_validation(
    target_values: Mapping[str, str],
) -> dict[str, str]:
    values = dict(target_values)
    for key, entry in load_value_state().items():
        if is_locked_source(entry["source"]):
            values[key] = str(entry["value"])
    return values


def validate_values(values: Mapping[str, str]) -> tuple[bool, list[str]]:
    """Validate proposed env values against the Settings model."""
    kwargs: dict[str, Any] = {"_env_file": None}
    for field in FIELDS:
        input_key = field_input_key(field)
        if input_key is None:
            continue
        kwargs[input_key] = values.get(field.key, "")

    try:
        Settings(**kwargs)
    except ValidationError as exc:
        return False, format_validation_errors(exc)
    return True, []


def validate_updates(updates: Mapping[str, Any]) -> dict[str, Any]:
    """Validate partial admin updates and return a masked generated env preview."""
    target_values = _target_values_with_updates(updates)
    effective_values = _effective_values_for_validation(target_values)
    valid, errors = validate_values(effective_values)
    return {
        "valid": valid,
        "errors": errors,
        "env_preview": render_env_file(target_values, mask_secrets=True),
    }


def changed_pending_fields(updates: Mapping[str, Any]) -> list[str]:
    """Return changed fields that require manual runtime action."""
    state = load_value_state()
    pending: list[str] = []
    for key, value in updates.items():
        field = FIELD_BY_KEY.get(key)
        if field is None or not (field.restart_required or field.session_sensitive):
            continue
        if normalize_for_env(value) == str(state[key]["value"]):
            continue
        pending.append(key)
    return pending


def write_managed_env(updates: Mapping[str, Any]) -> dict[str, Any]:
    """Validate and atomically write the admin-managed env file."""
    validation = validate_updates(updates)
    if not validation["valid"]:
        return validation | {"applied": False, "pending_fields": []}

    target_values = _target_values_with_updates(updates)
    pending_fields = changed_pending_fields(updates)
    path = managed_env_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(render_env_file(target_values), encoding="utf-8")
    os.replace(temp_path, path)
    return {
        "applied": True,
        "valid": True,
        "errors": [],
        "env_preview": render_env_file(target_values, mask_secrets=True),
        "path": str(path),
        "pending_fields": pending_fields,
    }


def _quote_env_value(value: str) -> str:
    if value == "":
        return ""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    if any(char.isspace() for char in value) or any(
        char in value for char in ('"', "#", "=", "$")
    ):
        return f'"{escaped}"'
    return value


def render_env_file(values: Mapping[str, str], *, mask_secrets: bool = False) -> str:
    """Render a complete grouped env file."""
    lines: list[str] = [
        "# Managed by Free Claude Code /admin.",
        "# Edit in the server UI when possible.",
        "",
    ]
    fields_by_section: dict[str, list[ConfigFieldSpec]] = {
        section.section_id: [] for section in SECTIONS
    }
    for field in FIELDS:
        fields_by_section.setdefault(field.section_id, []).append(field)

    for section in SECTIONS:
        lines.append(f"# {section.label}")
        for field in fields_by_section.get(section.section_id, []):
            value = values.get(field.key, field.default)
            if mask_secrets and field.secret and value:
                value = MASKED_SECRET
            lines.append(f"{field.key}={_quote_env_value(value)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
