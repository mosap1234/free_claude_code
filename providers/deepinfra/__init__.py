"""DeepInfra (OpenAI-compatible) adapter."""

from providers.defaults import DEEPINFRA_DEFAULT_BASE

from .client import DeepInfraProvider

__all__ = ["DEEPINFRA_DEFAULT_BASE", "DeepInfraProvider"]
