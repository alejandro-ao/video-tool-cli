"""Backend-neutral transcription data models."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class TranscriptSegment:
    """One timestamped transcript segment."""

    start: float
    end: float
    text: str


@dataclass(frozen=True)
class TranscriptResult:
    """Normalized output returned by every transcription backend."""

    text: str
    segments: list[TranscriptSegment]
    backend: str
    model: str
    language: str | None = None


@dataclass(frozen=True)
class TranscriptionModel:
    """A model exposed through the public transcription registry."""

    id: str
    backend: str
    repository: str
    local: bool
    multilingual: bool
    platforms: tuple[str, ...]
    extra: str | None
    description: str
