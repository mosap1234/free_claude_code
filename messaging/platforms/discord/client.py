"""Internal discord.py client forwarded into DiscordPlatform."""

from typing import TYPE_CHECKING, Any

import discord
from loguru import logger

from .constants import DISCORD_AVAILABLE, _discord_module

if TYPE_CHECKING:
    from messaging.platforms.discord.platform import DiscordPlatform

_DiscordClient: Any | None = None

if DISCORD_AVAILABLE and _discord_module is not None:

    class _DiscordClient(discord.Client):
        """Internal Discord client that forwards events to DiscordPlatform."""

        def __init__(self, platform: DiscordPlatform, intents: discord.Intents) -> None:
            super().__init__(intents=intents)
            self._platform = platform

        async def on_ready(self) -> None:
            """Called when the bot is ready."""
            self._platform._connected = True
            logger.info("Discord platform connected")

        async def on_message(self, message: discord.Message) -> None:
            """Handle incoming Discord messages."""
            await self._platform._handle_client_message(message)
else:
    _DiscordClient = None


__all__ = ["_DiscordClient"]
