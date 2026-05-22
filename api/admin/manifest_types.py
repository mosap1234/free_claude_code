"""Admin UI manifest types (sections and env-backed field specs)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

FieldType = Literal[
    "text",
    "secret",
    "number",
    "boolean",
    "tri_boolean",
    "select",
    "textarea",
]
SourceType = Literal[
    "default",
    "template",
    "repo_env",
    "managed_env",
    "explicit_env_file",
    "process",
]

MASKED_SECRET = "********"


@dataclass(frozen=True, slots=True)
class ConfigSectionSpec:
    """A group of config fields rendered together in the admin UI."""

    section_id: str
    label: str
    description: str
    advanced: bool = False


@dataclass(frozen=True, slots=True)
class ConfigFieldSpec:
    """Typed metadata for one env-backed admin setting."""

    key: str
    label: str
    section_id: str
    field_type: FieldType = "text"
    settings_attr: str | None = None
    default: str = ""
    options: tuple[str, ...] = ()
    secret: bool = False
    advanced: bool = False
    restart_required: bool = False
    session_sensitive: bool = False
    description: str = ""


SECTIONS: tuple[ConfigSectionSpec, ...] = (
    ConfigSectionSpec(
        "providers",
        "Providers",
        "Provider keys, local endpoints, and proxy settings.",
    ),
    ConfigSectionSpec(
        "models",
        "Model Routing",
        "Provider-prefixed models used for Claude model tiers.",
    ),
    ConfigSectionSpec(
        "thinking",
        "Thinking",
        "Global and tier-specific thinking behavior.",
    ),
    ConfigSectionSpec(
        "runtime",
        "Runtime",
        "Server API token, rate limits, timeouts, and process settings.",
    ),
    ConfigSectionSpec(
        "messaging",
        "Messaging",
        "Discord, Telegram, CLI workspace, and session settings.",
    ),
    ConfigSectionSpec(
        "voice",
        "Voice",
        "Voice note transcription settings.",
    ),
    ConfigSectionSpec(
        "web_tools",
        "Web Tools",
        "Local Anthropic web_search and web_fetch behavior.",
    ),
    ConfigSectionSpec(
        "diagnostics",
        "Diagnostics",
        "Logging and debugging flags.",
        advanced=True,
    ),
    ConfigSectionSpec(
        "smoke",
        "Smoke Tests",
        "Optional live smoke-test model overrides.",
        advanced=True,
    ),
)
