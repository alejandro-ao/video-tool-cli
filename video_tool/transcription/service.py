"""Transcription orchestration and VTT rendering."""

from __future__ import annotations

from pathlib import Path

from .models import TranscriptResult, TranscriptSegment
from .recommendation import recommend_model
from .registry import create_backend, resolve_model


class TranscriptionService:
    """Resolve a model, execute its backend, and normalize output."""

    def __init__(self, *, groq_client: object | None = None) -> None:
        self.groq_client = groq_client

    def transcribe(
        self,
        audio_path: Path,
        *,
        backend: str = "auto",
        model: str = "auto",
        language: str = "auto",
        device: str = "auto",
        compute_type: str = "auto",
    ) -> TranscriptResult:
        if model == "auto" and backend == "auto":
            model = recommend_model(language=language, available_only=True).model_id
        selected = resolve_model(model, backend)
        engine = create_backend(selected.backend, groq_client=self.groq_client)
        return engine.transcribe(
            audio_path,
            model=selected.repository,
            language=language,
            device=device,
            compute_type=compute_type,
        )


def render_vtt(result: TranscriptResult, *, fallback_duration: float | None = None) -> str:
    """Render normalized transcript segments as WebVTT captions."""
    segments = _valid_segments(result.segments)
    if not segments and result.text:
        segments = [TranscriptSegment(0.0, fallback_duration or 99 * 3600, result.text)]
    lines = ["WEBVTT", ""]
    for segment in segments:
        lines.extend((_timestamp(segment.start) + " --> " + _timestamp(segment.end), segment.text, ""))
    return "\n".join(lines)


def _valid_segments(segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
    valid: list[TranscriptSegment] = []
    for segment in segments:
        text = segment.text.replace("\x00", "").strip()
        start = max(0.0, segment.start)
        end = max(start, segment.end)
        if text and end > start:
            valid.append(TranscriptSegment(start, end, text))
    return sorted(valid, key=lambda item: (item.start, item.end))


def _timestamp(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    remaining = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{remaining:06.3f}"
