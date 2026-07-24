"""Parakeet backend optimized for Apple Silicon with MLX."""

from __future__ import annotations

from pathlib import Path

from ..base import MissingBackendDependency
from ..models import TranscriptResult, TranscriptSegment


class MlxParakeetBackend:
    name = "mlx-parakeet"

    def transcribe(
        self,
        audio_path: Path,
        *,
        model: str,
        language: str | None = None,
        device: str = "auto",
        compute_type: str = "auto",
    ) -> TranscriptResult:
        del device, compute_type
        try:
            from parakeet_mlx import from_pretrained
        except ImportError as exc:
            raise MissingBackendDependency(self.name, "transcription-mlx") from exc
        result = from_pretrained(model).transcribe(str(audio_path), chunk_duration=120.0, overlap_duration=15.0)
        segments = [
            TranscriptSegment(float(item.start), float(item.end), str(item.text).strip())
            for item in result.sentences
            if item.text.strip()
        ]
        return TranscriptResult(str(result.text).strip(), segments, self.name, model, language or "en")
