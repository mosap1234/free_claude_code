"""Transcript primitives for messaging renders (segments + truncatable buffers)."""

from __future__ import annotations

from .transcript_buffer import TranscriptBuffer
from .transcript_segments import RenderCtx

__all__ = ["RenderCtx", "TranscriptBuffer"]
