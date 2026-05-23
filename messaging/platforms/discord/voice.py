"""Discord voice/audio attachment ingestion."""

import contextlib
import tempfile
from pathlib import Path
from typing import Any, cast

from loguru import logger

from core.anthropic import format_user_error_preview

from ...models import IncomingMessage
from ...rendering.discord_markdown import format_status_discord
from .constants import AUDIO_EXTENSIONS


class DiscordVoiceMixin:
    """Voice note handling mixed into DiscordPlatform."""

    _voice_note_enabled: bool
    _message_handler: Any
    _voice_transcription: Any
    _whisper_model: str
    _whisper_device: str
    _log_raw_messaging_content: bool
    _log_api_error_tracebacks: bool
    _pending_voice: Any

    def _get_audio_attachment(self, message: Any) -> Any | None:
        """Return first audio attachment, or None."""
        for att in message.attachments:
            ct = (att.content_type or "").lower()
            fn = (att.filename or "").lower()
            if ct.startswith("audio/") or any(
                fn.endswith(ext) for ext in AUDIO_EXTENSIONS
            ):
                return att
        return None

    async def _handle_voice_note(
        self, message: Any, attachment: Any, channel_id: str
    ) -> bool:
        """Handle voice/audio attachment. Returns True if handled."""
        plat = cast(Any, self)
        if not self._voice_note_enabled:
            await message.reply("Voice notes are disabled.")
            return True

        if not self._message_handler:
            return False

        status_msg_id = await plat.queue_send_message(
            channel_id,
            format_status_discord("Transcribing voice note..."),
            reply_to=str(message.id),
            fire_and_forget=False,
        )

        user_id = str(message.author.id)
        message_id = str(message.id)
        await plat._register_pending_voice(channel_id, message_id, str(status_msg_id))
        reply_to = (
            str(message.reference.message_id)
            if message.reference and message.reference.message_id
            else None
        )

        ext = ".ogg"
        fn = (attachment.filename or "").lower()
        for e in AUDIO_EXTENSIONS:
            if fn.endswith(e):
                ext = e
                break
        ct = attachment.content_type or "audio/ogg"
        if "mp4" in ct or "m4a" in fn:
            ext = ".m4a" if "m4a" in fn else ".mp4"
        elif "mp3" in ct or fn.endswith(".mp3"):
            ext = ".mp3"

        with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            await attachment.save(str(tmp_path))

            transcribed = await self._voice_transcription.transcribe(
                tmp_path,
                ct,
                whisper_model=self._whisper_model,
                whisper_device=self._whisper_device,
            )

            if not await plat._is_voice_still_pending(channel_id, message_id):
                await plat.queue_delete_message(channel_id, str(status_msg_id))
                return True

            await self._pending_voice.complete(
                channel_id, message_id, str(status_msg_id)
            )

            incoming = IncomingMessage(
                text=transcribed,
                chat_id=channel_id,
                user_id=user_id,
                message_id=message_id,
                platform="discord",
                reply_to_message_id=reply_to,
                username=message.author.display_name,
                raw_event=message,
                status_message_id=status_msg_id,
            )

            if self._log_raw_messaging_content:
                logger.info(
                    "DISCORD_VOICE: chat_id={} message_id={} transcribed={!r}",
                    channel_id,
                    message_id,
                    (
                        transcribed[:80] + "..."
                        if len(transcribed) > 80
                        else transcribed
                    ),
                )
            else:
                logger.info(
                    "DISCORD_VOICE: chat_id={} message_id={} transcribed_len={}",
                    channel_id,
                    message_id,
                    len(transcribed),
                )

            await self._message_handler(incoming)
            return True
        except ValueError as e:
            await message.reply(format_user_error_preview(e))
            return True
        except ImportError as e:
            await message.reply(format_user_error_preview(e))
            return True
        except Exception as e:
            if self._log_api_error_tracebacks:
                logger.error("Voice transcription failed: {}", e)
            else:
                logger.error(
                    "Voice transcription failed: exc_type={}", type(e).__name__
                )
            await message.reply(
                "Could not transcribe voice note. Please try again or send text."
            )
            return True
        finally:
            with contextlib.suppress(OSError):
                tmp_path.unlink(missing_ok=True)
