"""Transcript primitives for messaging renders (segments + truncatable buffers)."""

from .transcript_buffer import TranscriptBuffer
from .transcript_segments import RenderCtx
from .ui_updates import ThrottledTranscriptEditor

__all__ = ["RenderCtx", "ThrottledTranscriptEditor", "TranscriptBuffer"]
