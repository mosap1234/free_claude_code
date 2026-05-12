"""Generic OpenAI-compatible provider exports."""

from providers.defaults import OPENAI_COMPAT_DEFAULT_BASE

from .client import OpenAICompatProvider

__all__ = [
    "OPENAI_COMPAT_DEFAULT_BASE",
    "OpenAICompatProvider",
]
