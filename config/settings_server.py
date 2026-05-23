"""HTTP bind and proxy auth."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ServerBindMixin(BaseModel):
    host: str = "0.0.0.0"
    port: int = 8082
    anthropic_auth_token: str = Field(
        default="", validation_alias="ANTHROPIC_AUTH_TOKEN"
    )
