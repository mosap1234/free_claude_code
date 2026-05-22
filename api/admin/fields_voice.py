"""Admin fields: voice."""

from api.admin.manifest_types import ConfigFieldSpec

FIELDS: tuple[ConfigFieldSpec, ...] = (
    ConfigFieldSpec(
        "VOICE_NOTE_ENABLED",
        "Voice Notes",
        "voice",
        "boolean",
        settings_attr="voice_note_enabled",
        default="false",
        session_sensitive=True,
    ),
    ConfigFieldSpec(
        "WHISPER_DEVICE",
        "Whisper Device",
        "voice",
        "select",
        settings_attr="whisper_device",
        default="nvidia_nim",
        options=("cpu", "cuda", "nvidia_nim"),
        session_sensitive=True,
    ),
    ConfigFieldSpec(
        "WHISPER_MODEL",
        "Whisper Model",
        "voice",
        settings_attr="whisper_model",
        default="openai/whisper-large-v3",
        session_sensitive=True,
    ),
    ConfigFieldSpec(
        "HF_TOKEN",
        "Hugging Face Token",
        "voice",
        "secret",
        settings_attr="hf_token",
        secret=True,
        session_sensitive=True,
    ),
)
