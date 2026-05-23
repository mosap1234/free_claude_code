"""Voice-note transcription knobs."""

from pydantic import BaseModel, Field


class VoiceNoteMixin(BaseModel):
    voice_note_enabled: bool = Field(
        default=True, validation_alias="VOICE_NOTE_ENABLED"
    )
    whisper_device: str = Field(default="cpu", validation_alias="WHISPER_DEVICE")
    whisper_model: str = Field(default="base", validation_alias="WHISPER_MODEL")
    hf_token: str = Field(default="", validation_alias="HF_TOKEN")
