"""Provider API credential fields flattened onto Settings."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ProviderCredentialsMixin(BaseModel):
    """Env-backed upstream API keys."""

    open_router_api_key: str = Field(default="", validation_alias="OPENROUTER_API_KEY")
    deepseek_api_key: str = Field(default="", validation_alias="DEEPSEEK_API_KEY")
    kimi_api_key: str = Field(default="", validation_alias="KIMI_API_KEY")
    wafer_api_key: str = Field(default="", validation_alias="WAFER_API_KEY")
    # Same key from opencode.ai/auth; zen uses prefix ``opencode/``, Go uses ``opencode_go/``.
    opencode_api_key: str = Field(default="", validation_alias="OPENCODE_API_KEY")
    zai_api_key: str = Field(default="", validation_alias="ZAI_API_KEY")
    fireworks_api_key: str = Field(default="", validation_alias="FIREWORKS_API_KEY")

    # NVIDIA NIM chat + optional NIM voice transcription
    nvidia_nim_api_key: str = ""
