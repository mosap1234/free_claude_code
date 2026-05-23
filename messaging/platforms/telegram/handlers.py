"""Telegram update handlers (text, commands, voice)."""

import contextlib
import tempfile
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from loguru import logger

from core.anthropic import format_user_error_preview

from ...models import IncomingMessage
from ...rendering.telegram_markdown import escape_md_v2, format_status

if TYPE_CHECKING:
    from telegram import Update
    from telegram.ext import ContextTypes


class TelegramHandlersMixin:
    """Ingress handlers mixed into :class:`~messaging.platforms.telegram.platform.TelegramPlatform`."""

    _message_handler: Callable[[IncomingMessage], Awaitable[None]] | None
    allowed_user_id: str | None
    _log_raw_messaging_content: bool
    _log_api_error_tracebacks: bool
    _voice_note_enabled: bool
    _whisper_model: str
    _whisper_device: str
    _voice_transcription: Any
    _pending_voice: Any

    async def _on_start_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle /start command."""
        if update.message:
            await update.message.reply_text("👋 Hello! I am the Claude Code Proxy Bot.")
        await self._on_telegram_message(update, context)

    async def _on_telegram_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle incoming updates."""
        if (
            not update.message
            or not update.message.text
            or not update.effective_user
            or not update.effective_chat
        ):
            return

        user_id = str(update.effective_user.id)
        chat_id = str(update.effective_chat.id)

        if self.allowed_user_id and user_id != str(self.allowed_user_id).strip():
            logger.warning(f"Unauthorized access attempt from {user_id}")
            return

        message_id = str(update.message.message_id)
        reply_to = (
            str(update.message.reply_to_message.message_id)
            if update.message.reply_to_message
            else None
        )
        thread_id = (
            str(update.message.message_thread_id)
            if getattr(update.message, "message_thread_id", None) is not None
            else None
        )
        raw_text = update.message.text or ""
        if self._log_raw_messaging_content:
            text_preview = raw_text[:80]
            if len(raw_text) > 80:
                text_preview += "..."
            logger.info(
                "TELEGRAM_MSG: chat_id={} message_id={} reply_to={} text_preview={!r}",
                chat_id,
                message_id,
                reply_to,
                text_preview,
            )
        else:
            logger.info(
                "TELEGRAM_MSG: chat_id={} message_id={} reply_to={} text_len={}",
                chat_id,
                message_id,
                reply_to,
                len(raw_text),
            )

        if not self._message_handler:
            return

        incoming = IncomingMessage(
            text=update.message.text,
            chat_id=chat_id,
            user_id=user_id,
            message_id=message_id,
            platform="telegram",
            reply_to_message_id=reply_to,
            message_thread_id=thread_id,
            raw_event=update,
        )

        try:
            await self._message_handler(incoming)
        except Exception as e:
            if self._log_api_error_tracebacks:
                logger.error("Error handling message: {}", e)
            else:
                logger.error("Error handling message: exc_type={}", type(e).__name__)
            with contextlib.suppress(Exception):
                impl = cast(Any, self)
                await impl.send_message(
                    chat_id,
                    f"❌ *{escape_md_v2('Error:')}* {escape_md_v2(format_user_error_preview(e))}",
                    reply_to=incoming.message_id,
                    message_thread_id=thread_id,
                    parse_mode="MarkdownV2",
                )

    async def _on_telegram_voice(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle incoming voice messages."""
        impl = cast(Any, self)
        if (
            not update.message
            or not update.message.voice
            or not update.effective_user
            or not update.effective_chat
        ):
            return

        if not self._voice_note_enabled:
            await update.message.reply_text("Voice notes are disabled.")
            return

        user_id = str(update.effective_user.id)
        chat_id = str(update.effective_chat.id)

        if self.allowed_user_id and user_id != str(self.allowed_user_id).strip():
            logger.warning(f"Unauthorized voice access attempt from {user_id}")
            return

        if not self._message_handler:
            return

        thread_id = (
            str(update.message.message_thread_id)
            if getattr(update.message, "message_thread_id", None) is not None
            else None
        )
        status_msg_id = await impl.queue_send_message(
            chat_id,
            format_status("⏳", "Transcribing voice note..."),
            reply_to=str(update.message.message_id),
            parse_mode="MarkdownV2",
            fire_and_forget=False,
            message_thread_id=thread_id,
        )

        message_id = str(update.message.message_id)
        await impl._register_pending_voice(chat_id, message_id, str(status_msg_id))
        reply_to = (
            str(update.message.reply_to_message.message_id)
            if update.message.reply_to_message
            else None
        )

        voice = update.message.voice
        suffix = ".ogg"
        if voice.mime_type and "mpeg" in voice.mime_type:
            suffix = ".mp3"
        elif voice.mime_type and "mp4" in voice.mime_type:
            suffix = ".mp4"

        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            tg_file = await context.bot.get_file(voice.file_id)
            await tg_file.download_to_drive(custom_path=str(tmp_path))

            transcribed = await self._voice_transcription.transcribe(
                tmp_path,
                voice.mime_type or "audio/ogg",
                whisper_model=self._whisper_model,
                whisper_device=self._whisper_device,
            )

            if not await impl._is_voice_still_pending(chat_id, message_id):
                await impl.queue_delete_message(chat_id, str(status_msg_id))
                return

            await self._pending_voice.complete(chat_id, message_id, str(status_msg_id))

            incoming = IncomingMessage(
                text=transcribed,
                chat_id=chat_id,
                user_id=user_id,
                message_id=message_id,
                platform="telegram",
                reply_to_message_id=reply_to,
                message_thread_id=thread_id,
                raw_event=update,
                status_message_id=status_msg_id,
            )

            if self._log_raw_messaging_content:
                logger.info(
                    "TELEGRAM_VOICE: chat_id={} message_id={} transcribed={!r}",
                    chat_id,
                    message_id,
                    (
                        transcribed[:80] + "..."
                        if len(transcribed) > 80
                        else transcribed
                    ),
                )
            else:
                logger.info(
                    "TELEGRAM_VOICE: chat_id={} message_id={} transcribed_len={}",
                    chat_id,
                    message_id,
                    len(transcribed),
                )

            await self._message_handler(incoming)
        except ValueError as e:
            await update.message.reply_text(format_user_error_preview(e))
        except ImportError as e:
            await update.message.reply_text(format_user_error_preview(e))
        except Exception as e:
            if self._log_api_error_tracebacks:
                logger.error("Voice transcription failed: {}", e)
            else:
                logger.error(
                    "Voice transcription failed: exc_type={}", type(e).__name__
                )
            await update.message.reply_text(
                "Could not transcribe voice note. Please try again or send text."
            )
        finally:
            with contextlib.suppress(OSError):
                tmp_path.unlink(missing_ok=True)
