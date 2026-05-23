"""Stable import paths for ingress domain errors (implementation in :mod:`api.ingress`)."""

from api.ingress.errors import (
    GatewayInvalidProxyApiKey,
    GatewayMissingProxyApiKey,
    IngressDetailError,
    ProviderResolutionAuthFailure,
)

__all__ = [
    "GatewayInvalidProxyApiKey",
    "GatewayMissingProxyApiKey",
    "IngressDetailError",
    "ProviderResolutionAuthFailure",
]
