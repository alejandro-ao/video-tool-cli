"""Interfaces and shared errors for transcription backends."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from .models import TranscriptResult


class TranscriptionError(RuntimeError):
    """Raised when a backend cannot transcribe an input."""


class MissingBackendDependency(TranscriptionError):
    """Raised when an optional backend dependency is not installed."""

    def __init__(self, backend: str, extra: str) -> None:
        super().__init__(
            f"The '{backend}' backend is not installed. Install it with: pip install 'video-tool[{extra}]'"
        )


class TranscriptionBackend(Protocol):
    """Contract implemented by local and remote speech recognition engines."""

    name: str

    def transcribe(
        self,
        audio_path: Path,
        *,
        model: str,
        language: str | None = None,
        device: str = "auto",
        compute_type: str = "auto",
    ) -> TranscriptResult:
        """Transcribe one audio file and return normalized segments."""
