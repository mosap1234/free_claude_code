"""Discord platform constants and discord.py module shim."""

from typing import Any

AUDIO_EXTENSIONS = (".ogg", ".mp4", ".mp3", ".wav", ".m4a")

_discord_module: Any = None
try:
    import discord as _discord_import

    _discord_module = _discord_import
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False

DISCORD_MESSAGE_LIMIT = 2000


def _get_discord() -> Any:
    """Return the discord module. Raises if not available."""
    if not DISCORD_AVAILABLE or _discord_module is None:
        raise ImportError(
            "discord.py is required. Install with: pip install discord.py"
        )
    return _discord_module


def _parse_allowed_channels(raw: str | None) -> set[str]:
    """Parse comma-separated channel IDs into a set of strings."""
    if not raw or not raw.strip():
        return set()
    return {s.strip() for s in raw.split(",") if s.strip()}


__all__ = [
    "AUDIO_EXTENSIONS",
    "DISCORD_AVAILABLE",
    "DISCORD_MESSAGE_LIMIT",
    "_discord_module",
    "_get_discord",
    "_parse_allowed_channels",
]
