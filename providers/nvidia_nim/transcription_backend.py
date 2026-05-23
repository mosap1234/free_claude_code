"""Concrete :class:`~messaging.voice_backend.TranscriptionBackend` using NVIDIA NIM / Riva."""

from pathlib import Path

from .voice import transcribe_audio_file


class NvidiaNimTranscriptionBackend:
    """Injectable ASR shim wired from ``api.runtime`` into messaging platforms."""

    __slots__ = ()

    def transcribe_audio_file(
        self,
        file_path: Path,
        nim_model_id: str,
        *,
        api_key: str,
    ) -> str:
        return transcribe_audio_file(file_path, nim_model_id, api_key=api_key)
