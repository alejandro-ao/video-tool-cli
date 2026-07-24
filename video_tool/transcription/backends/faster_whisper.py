"""Portable CTranslate2 Whisper backend."""

from __future__ import annotations

from pathlib import Path

from ..base import MissingBackendDependency
from ..models import TranscriptResult, TranscriptSegment


class FasterWhisperBackend:
    name = "faster-whisper"

    def transcribe(
        self,
        audio_path: Path,
        *,
        model: str,
        language: str | None = None,
        device: str = "auto",
        compute_type: str = "auto",
    ) -> TranscriptResult:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise MissingBackendDependency(self.name, "transcription-faster-whisper") from exc
        selected_device = "cpu" if device == "auto" else device
        selected_compute = "int8" if compute_type == "auto" and selected_device == "cpu" else compute_type
        if selected_compute == "auto":
            selected_compute = "float16"
        engine = WhisperModel(model, device=selected_device, compute_type=selected_compute)
        raw_segments, info = engine.transcribe(
            str(audio_path), language=None if language in (None, "auto") else language
        )
        segments = [
            TranscriptSegment(float(item.start), float(item.end), item.text.strip())
            for item in raw_segments
            if item.text.strip()
        ]
        return TranscriptResult(
            " ".join(item.text for item in segments), segments, self.name, model, getattr(info, "language", language)
        )
