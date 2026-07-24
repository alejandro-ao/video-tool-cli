"""Groq-hosted Whisper backend."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from pydub import AudioSegment

from ..base import TranscriptionError
from ..models import TranscriptResult, TranscriptSegment

_MAX_UPLOAD_BYTES = 24 * 1024 * 1024
_CHUNK_MILLISECONDS = 10 * 60 * 1000


class GroqBackend:
    """Transcribe through the existing Groq API client."""

    name = "groq"

    def __init__(self, client: object | None) -> None:
        self.client = client

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
        if self.client is None:
            raise TranscriptionError("Groq is selected but no API key is configured. Run 'video-tool config keys'.")
        if audio_path.stat().st_size <= _MAX_UPLOAD_BYTES:
            return self._transcribe_file(audio_path, model=model, language=language)

        audio = AudioSegment.from_file(str(audio_path))
        segments: list[TranscriptSegment] = []
        texts: list[str] = []
        with tempfile.TemporaryDirectory(prefix="video-tool-groq-", dir=audio_path.parent) as temp_dir:
            for index, start_ms in enumerate(range(0, len(audio), _CHUNK_MILLISECONDS)):
                chunk_path = Path(temp_dir) / f"chunk-{index}.mp3"
                audio[start_ms : start_ms + _CHUNK_MILLISECONDS].export(chunk_path, format="mp3")
                chunk = self._transcribe_file(chunk_path, model=model, language=language)
                offset = start_ms / 1000
                segments.extend(
                    TranscriptSegment(item.start + offset, item.end + offset, item.text) for item in chunk.segments
                )
                if chunk.text:
                    texts.append(chunk.text)
        return TranscriptResult(" ".join(texts), segments, self.name, model, language)

    def _transcribe_file(self, audio_path: Path, *, model: str, language: str | None) -> TranscriptResult:
        kwargs: dict[str, Any] = {
            "model": model,
            "response_format": "verbose_json",
            "timestamp_granularities": ["segment"],
        }
        if language and language != "auto":
            kwargs["language"] = language
        with audio_path.open("rb") as audio_file:
            kwargs["file"] = audio_file
            response = self.client.audio.transcriptions.create(**kwargs)  # type: ignore[attr-defined]
        raw_segments = _value(response, "segments") or []
        segments = [
            TranscriptSegment(
                float(_value(item, "start")),
                float(_value(item, "end")),
                str(_value(item, "text")).strip(),
            )
            for item in raw_segments
            if _value(item, "start") is not None and _value(item, "end") is not None and _value(item, "text")
        ]
        text = str(_value(response, "text") or " ".join(item.text for item in segments)).strip()
        return TranscriptResult(text, segments, self.name, model, language)


def _value(value: object, key: str) -> Any:
    if isinstance(value, dict):
        return value.get(key)
    return getattr(value, key, None)
