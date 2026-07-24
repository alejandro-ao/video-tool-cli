"""Hugging Face Transformers Whisper backend."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..base import MissingBackendDependency
from ..models import TranscriptResult, TranscriptSegment


class TransformersBackend:
    name = "transformers"

    def transcribe(
        self,
        audio_path: Path,
        *,
        model: str,
        language: str | None = None,
        device: str = "auto",
        compute_type: str = "auto",
    ) -> TranscriptResult:
        del compute_type
        try:
            import torch
            from transformers import pipeline
        except ImportError as exc:
            raise MissingBackendDependency(self.name, "transcription-transformers") from exc
        selected_device: str | int = -1
        if device == "cuda" or (device == "auto" and torch.cuda.is_available()):
            selected_device = 0
        elif device == "mps" or (device == "auto" and torch.backends.mps.is_available()):
            selected_device = "mps"
        engine = pipeline("automatic-speech-recognition", model=model, device=selected_device)
        generate_kwargs: dict[str, Any] = {}
        if language and language != "auto":
            generate_kwargs["language"] = language
        result = engine(str(audio_path), return_timestamps=True, generate_kwargs=generate_kwargs)
        segments = []
        for item in result.get("chunks", []):
            timestamp = item.get("timestamp") or (None, None)
            if timestamp[0] is not None and timestamp[1] is not None and item.get("text"):
                segments.append(TranscriptSegment(float(timestamp[0]), float(timestamp[1]), item["text"].strip()))
        return TranscriptResult(str(result.get("text", "")).strip(), segments, self.name, model, language)
