"""Native NVIDIA NeMo Parakeet backend."""

from __future__ import annotations

from pathlib import Path

from ..base import MissingBackendDependency, TranscriptionError
from ..models import TranscriptResult, TranscriptSegment


class NemoBackend:
    name = "nemo"

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
            import nemo.collections.asr as nemo_asr
        except ImportError as exc:
            raise MissingBackendDependency(self.name, "transcription-nemo") from exc
        engine = nemo_asr.models.ASRModel.from_pretrained(model_name=model)
        results = engine.transcribe([str(audio_path)], timestamps=True)
        if not results:
            raise TranscriptionError("NeMo returned no transcription")
        hypothesis = results[0]
        timestamps = getattr(hypothesis, "timestamp", {}) or {}
        raw_segments = timestamps.get("segment") or timestamps.get("word") or []
        segments = [
            TranscriptSegment(
                float(item["start"]), float(item["end"]), str(item.get("segment") or item.get("word", "")).strip()
            )
            for item in raw_segments
            if item.get("start") is not None and item.get("end") is not None
        ]
        text = str(getattr(hypothesis, "text", hypothesis)).strip()
        return TranscriptResult(text, segments, self.name, model, language or "en")
