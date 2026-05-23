"""Shared helpers for admin env manifest read/write paths."""

from typing import Any

from pydantic import ValidationError

from config.settings import Settings

from .admin_manifest import MASKED_SECRET, ConfigFieldSpec, SourceType


def normalize_for_env(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def is_locked_source(source: SourceType) -> bool:
    return source in {"process", "explicit_env_file"}


def display_value(field: ConfigFieldSpec, value: str) -> str:
    if field.secret and value:
        return MASKED_SECRET
    return value


def field_input_key(field: ConfigFieldSpec) -> str | None:
    if field.settings_attr is None:
        return None
    model_field = Settings.model_fields[field.settings_attr]
    alias = model_field.validation_alias
    if alias is None:
        return field.settings_attr
    return str(alias)


def format_validation_errors(exc: ValidationError) -> list[str]:
    errors: list[str] = []
    for error in exc.errors():
        loc = ".".join(str(part) for part in error.get("loc", ()))
        message = str(error.get("msg", "Invalid value"))
        errors.append(f"{loc}: {message}" if loc else message)
    return errors
