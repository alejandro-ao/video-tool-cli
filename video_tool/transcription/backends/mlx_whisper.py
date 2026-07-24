"""Whisper backend optimized for Apple Silicon with MLX."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..base import MissingBackendDependency
from ..models import TranscriptResult, TranscriptSegment


class MlxWhisperBackend:
    name = "mlx-whisper"

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
            import mlx_whisper
        except ImportError as exc:
            raise MissingBackendDependency(self.name, "transcription-mlx") from exc
        options: dict[str, Any] = {"path_or_hf_repo": model}
        if language and language != "auto":
            options["language"] = language
        result = mlx_whisper.transcribe(str(audio_path), **options)
        segments = [
            TranscriptSegment(float(item["start"]), float(item["end"]), str(item["text"]).strip())
            for item in result.get("segments", [])
            if item.get("text")
        ]
        return TranscriptResult(
            str(result.get("text", "")).strip(), segments, self.name, model, result.get("language", language)
        )
