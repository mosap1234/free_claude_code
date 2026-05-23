"""Discord text message ingress handlers."""

import contextlib
from typing import Any, cast

from loguru import logger

from core.anthropic import format_user_error_preview

from ...models import IncomingMessage
from ...rendering.discord_markdown import format_status_discord


class DiscordHandlersMixin:
    """Message ingress mixed into DiscordPlatform."""

    allowed_channel_ids: set[str]
    _message_handler: Any
    _log_raw_messaging_content: bool
    _log_api_error_tracebacks: bool

    async def _handle_client_message(self, message: Any) -> None:
        """Adapter entry point used by the internal discord client."""
        await self._on_discord_message(message)

    async def _on_discord_message(self, message: Any) -> None:
        """Handle incoming Discord messages."""
        plat = cast(Any, self)
        if message.author.bot:
            return

        channel_id = str(message.channel.id)

        if not self.allowed_channel_ids or channel_id not in self.allowed_channel_ids:
            return

        # Handle voice/audio attachments when message has no text content
        if not message.content:
            audio_att = plat._get_audio_attachment(message)
            if audio_att:
                await plat._handle_voice_note(message, audio_att, channel_id)
                return
            return

        user_id = str(message.author.id)
        message_id = str(message.id)
        reply_to = (
            str(message.reference.message_id)
            if message.reference and message.reference.message_id
            else None
        )

        raw_content = message.content or ""
        if self._log_raw_messaging_content:
            text_preview = raw_content[:80]
            if len(raw_content) > 80:
                text_preview += "..."
            logger.info(
                "DISCORD_MSG: chat_id={} message_id={} reply_to={} text_preview={!r}",
                channel_id,
                message_id,
                reply_to,
                text_preview,
            )
        else:
            logger.info(
                "DISCORD_MSG: chat_id={} message_id={} reply_to={} text_len={}",
                channel_id,
                message_id,
                reply_to,
                len(raw_content),
            )

        if not self._message_handler:
            return

        incoming = IncomingMessage(
            text=message.content,
            chat_id=channel_id,
            user_id=user_id,
            message_id=message_id,
            platform="discord",
            reply_to_message_id=reply_to,
            username=message.author.display_name,
            raw_event=message,
        )

        try:
            await self._message_handler(incoming)
        except Exception as e:
            if self._log_api_error_tracebacks:
                logger.error("Error handling message: {}", e)
            else:
                logger.error("Error handling message: exc_type={}", type(e).__name__)
            with contextlib.suppress(Exception):
                await plat.send_message(
                    channel_id,
                    format_status_discord("Error:", format_user_error_preview(e)),
                    reply_to=message_id,
                )
