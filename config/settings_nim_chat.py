"""Nested NVIDIA NIM chat knobs."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .nim import NimSettings


class NimChatMixin(BaseModel):
    nim: NimSettings = Field(default_factory=NimSettings)
