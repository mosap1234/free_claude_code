"""
Telegram Platform Adapter

Implements MessagingPlatform for Telegram using python-telegram-bot.
"""

import asyncio
import os

# Opt-in to future behavior for python-telegram-bot (retry_after as timedelta)
# This must be set BEFORE importing telegram.error
os.environ["PTB_TIMEDELTA"] = "1"

from collections.abc import Awaitable, Callable
from typing import Any

from loguru import logger

from ...models import IncomingMessage
from ...rendering.telegram_markdown import escape_md_v2
from ...voice import PendingVoiceRegistry, VoiceTranscriptionService
from ...voice_backend import TranscriptionBackend
from ..base import MessagingPlatform
from .handlers import TelegramHandlersMixin
from .outbound import TelegramOutboundMixin

# Optional import - python-telegram-bot may not be installed
try:
    from telegram.error import NetworkError
    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        filters,
    )
    from telegram.request import HTTPXRequest

    TELEGRAM_AVAILABLE = True
except ImportError:
    TELEGRAM_AVAILABLE = False


class TelegramPlatform(TelegramOutboundMixin, TelegramHandlersMixin, MessagingPlatform):
    """
    Telegram messaging platform adapter.

    Uses python-telegram-bot (BoT API) for Telegram access.
    Requires a Bot Token from @BotFather.
    """

    name = "telegram"

    def __init__(
        self,
        bot_token: str | None = None,
        allowed_user_id: str | None = None,
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
        if not TELEGRAM_AVAILABLE:
            raise ImportError(
                "python-telegram-bot is required. Install with: pip install python-telegram-bot"
            )

        self.bot_token = bot_token
        self.allowed_user_id = allowed_user_id

        if not self.bot_token:
            # We don't raise here to allow instantiation for testing/conditional logic,
            # but start() will fail.
            logger.warning("TELEGRAM_BOT_TOKEN not set")

        self._application: Application | None = None
        self._message_handler: Callable[[IncomingMessage], Awaitable[None]] | None = (
            None
        )
        self._connected = False
        self._limiter: Any | None = None  # Will be MessagingRateLimiter
        # Pending voice transcriptions: (chat_id, msg_id) -> (voice_msg_id, status_msg_id)
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
        """Register a voice note as pending transcription (for /clear reply during transcription)."""
        await self._pending_voice.register(chat_id, voice_msg_id, status_msg_id)

    async def cancel_pending_voice(
        self, chat_id: str, reply_id: str
    ) -> tuple[str, str] | None:
        """Cancel a pending voice transcription. Returns (voice_msg_id, status_msg_id) if found."""
        return await self._pending_voice.cancel(chat_id, reply_id)

    async def _is_voice_still_pending(self, chat_id: str, voice_msg_id: str) -> bool:
        """Check if a voice note is still pending (not cancelled)."""
        return await self._pending_voice.is_pending(chat_id, voice_msg_id)

    async def start(self) -> None:
        """Initialize and connect to Telegram."""
        if not self.bot_token:
            raise ValueError("TELEGRAM_BOT_TOKEN is required")

        # Configure request with longer timeouts
        request = HTTPXRequest(
            connection_pool_size=8, connect_timeout=30.0, read_timeout=30.0
        )

        # Build Application
        builder = Application.builder().token(self.bot_token).request(request)
        self._application = builder.build()

        # Register Internal Handlers
        # We catch ALL text messages and commands to forward them
        self._application.add_handler(
            MessageHandler(filters.TEXT & (~filters.COMMAND), self._on_telegram_message)
        )
        self._application.add_handler(CommandHandler("start", self._on_start_command))
        # Catch-all for other commands if needed, or let them fall through
        self._application.add_handler(
            MessageHandler(filters.COMMAND, self._on_telegram_message)
        )
        # Voice note handler
        self._application.add_handler(
            MessageHandler(filters.VOICE, self._on_telegram_voice)
        )

        # Initialize internal components with retry logic
        max_retries = 3
        for attempt in range(max_retries):
            try:
                await self._application.initialize()
                await self._application.start()

                # Start polling (non-blocking way for integration)
                if self._application.updater:
                    await self._application.updater.start_polling(
                        drop_pending_updates=False
                    )

                self._connected = True
                break
            except (NetworkError, Exception) as e:
                if attempt < max_retries - 1:
                    wait_time = 2 * (attempt + 1)
                    logger.warning(
                        f"Connection failed (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s..."
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(f"Failed to connect after {max_retries} attempts")
                    raise

        # Initialize rate limiter
        from ...limiter import MessagingRateLimiter

        self._limiter = await MessagingRateLimiter.get_instance(
            rate_limit=self._messaging_rate_limit,
            rate_window=self._messaging_rate_window,
            log_messaging_error_details=self._log_messaging_error_details,
        )

        # Send startup notification
        try:
            target = self.allowed_user_id
            if target:
                startup_text = (
                    f"🚀 *{escape_md_v2('Claude Code Proxy is online!')}* "
                    f"{escape_md_v2('(Bot API)')}"
                )
                await self.send_message(
                    target,
                    startup_text,
                )
        except Exception as e:
            if self._log_api_error_tracebacks:
                logger.warning("Could not send startup message: {}", e)
            else:
                logger.warning(
                    "Could not send startup message: exc_type={}",
                    type(e).__name__,
                )

        logger.info("Telegram platform started (Bot API)")

    async def stop(self) -> None:
        """Stop the bot."""
        if self._application and self._application.updater:
            await self._application.updater.stop()
            await self._application.stop()
            await self._application.shutdown()

        self._connected = False
        logger.info("Telegram platform stopped")

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
