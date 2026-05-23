"""Protocols for injecting voice backends into messaging without provider imports."""

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class TranscriptionBackend(Protocol):
    """NVIDIA NIM / Riva (or compatible) offline transcription invoked from messaging."""

    def transcribe_audio_file(
        self,
        file_path: Path,
        nim_model_id: str,
        *,
        api_key: str,
    ) -> str:
        """Transcribe using the injected backend."""
        ...
