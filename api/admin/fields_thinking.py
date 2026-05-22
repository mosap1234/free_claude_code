"""Admin fields: thinking."""

from api.admin.manifest_types import ConfigFieldSpec

FIELDS: tuple[ConfigFieldSpec, ...] = (
    ConfigFieldSpec(
        "ENABLE_MODEL_THINKING",
        "Enable Thinking",
        "thinking",
        "boolean",
        settings_attr="enable_model_thinking",
        default="true",
    ),
    ConfigFieldSpec(
        "ENABLE_OPUS_THINKING",
        "Opus Thinking",
        "thinking",
        "tri_boolean",
        settings_attr="enable_opus_thinking",
        description="Blank inherits Enable Thinking.",
    ),
    ConfigFieldSpec(
        "ENABLE_SONNET_THINKING",
        "Sonnet Thinking",
        "thinking",
        "tri_boolean",
        settings_attr="enable_sonnet_thinking",
        description="Blank inherits Enable Thinking.",
    ),
    ConfigFieldSpec(
        "ENABLE_HAIKU_THINKING",
        "Haiku Thinking",
        "thinking",
        "tri_boolean",
        settings_attr="enable_haiku_thinking",
        description="Blank inherits Enable Thinking.",
    ),
)
