"""Model tier routing and tier-specific thinking overrides."""

from pydantic import BaseModel, ConfigDict


class ModelRoutingSettings(BaseModel):
    """Stable slice for Claude model tiers and thinking flags."""

    model_config = ConfigDict(frozen=True)

    model: str
    model_opus: str | None
    model_sonnet: str | None
    model_haiku: str | None
    enable_model_thinking: bool
    enable_opus_thinking: bool | None
    enable_sonnet_thinking: bool | None
    enable_haiku_thinking: bool | None
