"""Admin fields: runtime+flags."""

from api.admin.manifest_types import ConfigFieldSpec

FIELDS: tuple[ConfigFieldSpec, ...] = (
    ConfigFieldSpec(
        "FAST_PREFIX_DETECTION",
        "Fast Prefix Detection",
        "runtime",
        "boolean",
        settings_attr="fast_prefix_detection",
        default="true",
        advanced=True,
    ),
    ConfigFieldSpec(
        "ENABLE_NETWORK_PROBE_MOCK",
        "Network Probe Mock",
        "runtime",
        "boolean",
        settings_attr="enable_network_probe_mock",
        default="true",
        advanced=True,
    ),
    ConfigFieldSpec(
        "ENABLE_TITLE_GENERATION_SKIP",
        "Title Generation Skip",
        "runtime",
        "boolean",
        settings_attr="enable_title_generation_skip",
        default="true",
        advanced=True,
    ),
    ConfigFieldSpec(
        "ENABLE_SUGGESTION_MODE_SKIP",
        "Suggestion Mode Skip",
        "runtime",
        "boolean",
        settings_attr="enable_suggestion_mode_skip",
        default="true",
        advanced=True,
    ),
    ConfigFieldSpec(
        "ENABLE_FILEPATH_EXTRACTION_MOCK",
        "Filepath Extraction Mock",
        "runtime",
        "boolean",
        settings_attr="enable_filepath_extraction_mock",
        default="true",
        advanced=True,
    ),
)
