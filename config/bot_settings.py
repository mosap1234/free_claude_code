"""Bot / Discord / Telegram / voice knobs derived from Settings."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class BotSettings(BaseModel):
    """Stable slice for Telegram/Discord and voice-note configuration."""

    model_config = ConfigDict(frozen=True)

    telegram_bot_token: str | None
    allowed_telegram_user_id: str | None
    discord_bot_token: str | None
    allowed_discord_channels: str | None
    allowed_dir: str
    max_message_log_entries_per_chat: int | None
    voice_note_enabled: bool
    whisper_device: str
    whisper_model: str
    hf_token: str
