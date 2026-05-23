"""Proxy-side optimisation flags surfaced in Admin UI."""

from pydantic import BaseModel, ConfigDict


class AdminOptimizationSettings(BaseModel):
    """Bundled behavioural shortcuts (admin-visible runtime knobs)."""

    model_config = ConfigDict(frozen=True)

    fast_prefix_detection: bool
    enable_network_probe_mock: bool
    enable_title_generation_skip: bool
    enable_suggestion_mode_skip: bool
    enable_filepath_extraction_mock: bool
