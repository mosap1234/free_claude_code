"""Discord messaging platform package."""

from typing import Any

from .constants import (
    AUDIO_EXTENSIONS,
    DISCORD_AVAILABLE,
    DISCORD_MESSAGE_LIMIT,
    _discord_module,
    _parse_allowed_channels,
)
from .platform import DiscordPlatform


def _get_discord() -> Any:
    """Return the discord module; honors tests that patch constants module globals."""
    from . import constants as c

    return c._get_discord()


__all__ = [
    "AUDIO_EXTENSIONS",
    "DISCORD_AVAILABLE",
    "DISCORD_MESSAGE_LIMIT",
    "DiscordPlatform",
    "_discord_module",
    "_get_discord",
    "_parse_allowed_channels",
]
