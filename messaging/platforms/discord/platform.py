"""
Discord Platform Adapter

Implements MessagingPlatform for Discord using discord.py.
"""

import asyncio
import contextlib
from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger

from ...models import IncomingMessage
from ...voice import PendingVoiceRegistry, VoiceTranscriptionService
from ...voice_backend import TranscriptionBackend
from ..base import MessagingPlatform
from .client import _DiscordClient
from .constants import (
    DISCORD_AVAILABLE,
    _get_discord,
    _parse_allowed_channels,
)
from .handlers import DiscordHandlersMixin
from .outbound import DiscordOutboundMixin
from .voice import DiscordVoiceMixin


class DiscordPlatform(
    DiscordVoiceMixin,
    DiscordHandlersMixin,
    DiscordOutboundMixin,
    MessagingPlatform,
):
    """
    Discord messaging platform adapter.

    Uses discord.py for Discord access.
    Requires a Bot Token from Discord Developer Portal and message_content intent.
    """

    name = "discord"

    def __init__(
        self,
        bot_token: str | None = None,
        allowed_channel_ids: str | None = None,
        *,
        voice_note_enabled: bool = True,
        whisper_model: str = "base",
        whisper_device: str = "cpu",
        hf_token: str = "",
        nvidia_nim_api_key: str = "",
        nim_backend: TranscriptionBackend | None = None,
        messaging_rate_limit: int = 1,
        messaging_rate_window: float = 1.0,
        log_raw_messaging_content: bool = False,
        log_api_error_tracebacks: bool = False,
        log_messaging_error_details: bool = False,
    ):
        if not DISCORD_AVAILABLE:
            raise ImportError(
                "discord.py is required. Install with: pip install discord.py"
            )

        self.bot_token = bot_token
        self.allowed_channel_ids = _parse_allowed_channels(allowed_channel_ids)

        if not self.bot_token:
            logger.warning("DISCORD_BOT_TOKEN not set")

        discord = _get_discord()
        intents = discord.Intents.default()
        intents.message_content = True

        assert _DiscordClient is not None
        self._client = _DiscordClient(self, intents)
        self._message_handler: Callable[[IncomingMessage], Awaitable[None]] | None = (
            None
        )
        self._connected = False
        self._limiter: Any | None = None
        self._start_task: asyncio.Task | None = None
        self._pending_voice = PendingVoiceRegistry()
        self._voice_transcription = VoiceTranscriptionService(
            hf_token=hf_token,
            nvidia_nim_api_key=nvidia_nim_api_key,
            nim_backend=nim_backend,
        )
        self._voice_note_enabled = voice_note_enabled
        self._whisper_model = whisper_model
        self._whisper_device = whisper_device
        self._messaging_rate_limit = messaging_rate_limit
        self._messaging_rate_window = messaging_rate_window
        self._log_raw_messaging_content = log_raw_messaging_content
        self._log_api_error_tracebacks = log_api_error_tracebacks
        self._log_messaging_error_details = log_messaging_error_details

    async def _register_pending_voice(
        self, chat_id: str, voice_msg_id: str, status_msg_id: str
    ) -> None:
        """Register a voice note as pending transcription."""
        await self._pending_voice.register(chat_id, voice_msg_id, status_msg_id)

    async def cancel_pending_voice(
        self, chat_id: str, reply_id: str
    ) -> tuple[str, str] | None:
        """Cancel a pending voice transcription."""
        return await self._pending_voice.cancel(chat_id, reply_id)

    async def _is_voice_still_pending(self, chat_id: str, voice_msg_id: str) -> bool:
        """Check if a voice note is still pending (not cancelled)."""
        return await self._pending_voice.is_pending(chat_id, voice_msg_id)

    async def start(self) -> None:
        """Initialize and connect to Discord."""
        if not self.bot_token:
            raise ValueError("DISCORD_BOT_TOKEN is required")

        from ...limiter import MessagingRateLimiter

        self._limiter = await MessagingRateLimiter.get_instance(
            rate_limit=self._messaging_rate_limit,
            rate_window=self._messaging_rate_window,
            log_messaging_error_details=self._log_messaging_error_details,
        )

        self._start_task = asyncio.create_task(
            self._client.start(self.bot_token),
            name="discord-client-start",
        )

        max_wait = 30
        waited = 0
        while not self._connected and waited < max_wait:
            await asyncio.sleep(0.5)
            waited += 0.5

        if not self._connected:
            raise RuntimeError("Discord client failed to connect within timeout")

        logger.info("Discord platform started")

    async def stop(self) -> None:
        """Stop the bot."""
        if self._client.is_closed():
            self._connected = False
            return

        await self._client.close()
        if self._start_task and not self._start_task.done():
            try:
                await asyncio.wait_for(self._start_task, timeout=5.0)
            except TimeoutError, asyncio.CancelledError:
                self._start_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await self._start_task

        self._connected = False
        logger.info("Discord platform stopped")

    def on_message(
        self,
        handler: Callable[[IncomingMessage], Awaitable[None]],
    ) -> None:
        """Register a message handler callback."""
        self._message_handler = handler

    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected
