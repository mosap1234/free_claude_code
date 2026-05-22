"""Admin fields: models."""

from api.admin.manifest_types import ConfigFieldSpec

FIELDS: tuple[ConfigFieldSpec, ...] = (
    ConfigFieldSpec(
        "MODEL",
        "Default Model",
        "models",
        settings_attr="model",
        default="nvidia_nim/z-ai/glm4.7",
        description="Fallback provider/model route for all Claude model names.",
    ),
    ConfigFieldSpec(
        "MODEL_OPUS",
        "Opus Override",
        "models",
        settings_attr="model_opus",
        description="Optional provider/model route for Opus requests.",
    ),
    ConfigFieldSpec(
        "MODEL_SONNET",
        "Sonnet Override",
        "models",
        settings_attr="model_sonnet",
        description="Optional provider/model route for Sonnet requests.",
    ),
    ConfigFieldSpec(
        "MODEL_HAIKU",
        "Haiku Override",
        "models",
        settings_attr="model_haiku",
        description="Optional provider/model route for Haiku requests.",
    ),
)
