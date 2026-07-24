"""Audio extraction and multi-backend transcription helpers."""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from moviepy import VideoFileClip
from pydub import AudioSegment

from video_tool.config import get_transcription_config
from video_tool.transcription import TranscriptionService, TranscriptResult, TranscriptSegment, render_vtt

from .constants import SUPPORTED_AUDIO_SUFFIXES, SUPPORTED_VIDEO_SUFFIXES


class TranscriptMixin:
    """Generate VTT captions through configurable local or remote models."""

    def generate_transcript(
        self,
        video_path: str | None = None,
        output_path: str | None = None,
        *,
        backend: str | None = None,
        model: str | None = None,
        language: str | None = None,
        device: str | None = None,
        compute_type: str | None = None,
    ) -> str:
        """Transcribe video or audio with the selected backend.

        Local models are downloaded lazily by their runtime and cached for later runs.
        Temporary audio extracted from video is removed before returning.
        """
        input_file = self._resolve_transcription_input(video_path)
        if input_file is None:
            return ""
        if input_file.suffix.lower() not in SUPPORTED_AUDIO_SUFFIXES + SUPPORTED_VIDEO_SUFFIXES:
            logger.error(f"Unsupported transcription input: {input_file}")
            return ""

        audio_path, cleanup_audio = self._prepare_transcription_audio(input_file)
        if audio_path is None:
            return ""
        settings = get_transcription_config()
        try:
            result = TranscriptionService(groq_client=self.groq).transcribe(
                audio_path,
                backend=backend or settings.backend,
                model=model or settings.model,
                language=language or settings.language,
                device=device or settings.device,
                compute_type=compute_type or settings.compute_type,
            )
            transcript = render_vtt(result, fallback_duration=self._audio_duration(audio_path))
            resolved_output = Path(output_path) if output_path else self.output_dir / "transcript.vtt"
            resolved_output.parent.mkdir(parents=True, exist_ok=True)
            resolved_output.write_text(transcript, encoding="utf-8")
            self.last_transcription = result
            return str(resolved_output)
        except Exception as exc:
            logger.error(f"Error generating transcript: {exc}")
            return ""
        finally:
            if cleanup_audio:
                try:
                    audio_path.unlink(missing_ok=True)
                except OSError as exc:
                    logger.warning(f"Could not remove temporary audio file {audio_path}: {exc}")

    def _resolve_transcription_input(self, video_path: str | None) -> Path | None:
        if video_path:
            candidate = Path(video_path)
            if candidate.exists():
                return candidate
            logger.error(f"Input file does not exist: {candidate}")
            return None
        existing = self._find_existing_output()
        if existing:
            return existing
        for root in (self.output_dir, self.input_dir):
            candidates = sorted(
                path
                for suffix in SUPPORTED_VIDEO_SUFFIXES + SUPPORTED_AUDIO_SUFFIXES
                for path in root.glob(f"*{suffix}")
            )
            if candidates:
                return candidates[0]
        logger.error("No video or audio file found for transcript generation")
        return None

    def _prepare_transcription_audio(self, input_file: Path) -> tuple[Path | None, bool]:
        if input_file.suffix.lower() in SUPPORTED_AUDIO_SUFFIXES:
            return input_file, False
        audio_path = input_file.with_suffix(".mp3")
        try:
            with self.suppress_external_output():
                try:
                    video = VideoFileClip(str(input_file), audio=True, verbose=False)  # type: ignore[call-arg]
                except TypeError:
                    video = VideoFileClip(str(input_file))
                if video.audio is None:
                    logger.error("Video file has no audio track")
                    video.close()
                    return None, False
                try:
                    video.audio.write_audiofile(str(audio_path), logger=None)
                except TypeError:
                    video.audio.write_audiofile(str(audio_path))
                finally:
                    video.close()
            if not audio_path.exists() or audio_path.stat().st_size == 0:
                logger.error("Extracted audio file is empty")
                return None, True
            return audio_path, True
        except Exception as exc:
            logger.error(f"Error processing video file {input_file}: {exc}")
            return None, True

    @staticmethod
    def _audio_duration(audio_path: Path) -> float | None:
        try:
            return len(AudioSegment.from_file(str(audio_path))) / 1000
        except Exception:
            return None

    # Compatibility helpers retained for callers that used the previous mixin API.
    def _format_seconds_to_vtt(self, seconds: float) -> str:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours:02d}:{minutes:02d}:{seconds % 60:06.3f}"

    def _groq_verbose_json_to_vtt(self, response: object) -> str:
        """Convert a legacy Groq response through the normalized renderer."""
        raw_segments = response.get("segments", []) if isinstance(response, dict) else getattr(response, "segments", [])
        segments = [
            TranscriptSegment(
                float(item.get("start") if isinstance(item, dict) else item.start),
                float(item.get("end") if isinstance(item, dict) else item.end),
                str(item.get("text") if isinstance(item, dict) else item.text),
            )
            for item in raw_segments
        ]
        text = response.get("text", "") if isinstance(response, dict) else getattr(response, "text", "")
        return render_vtt(TranscriptResult(str(text), segments, "groq", "whisper-large-v3-turbo"))
