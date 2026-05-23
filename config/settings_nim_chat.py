"""Nested NVIDIA NIM chat knobs."""

from pydantic import BaseModel, Field

from .nim import NimSettings


class NimChatMixin(BaseModel):
    nim: NimSettings = Field(default_factory=NimSettings)
