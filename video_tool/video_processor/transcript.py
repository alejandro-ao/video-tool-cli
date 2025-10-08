from __future__ import annotations

import os
import re
from pathlib import Path
from typing import List, Optional

from .shared import AudioSegment, VideoFileClip, logger


class TranscriptMixin:
    """Audio extraction and transcript generation helpers."""

    def generate_transcript(self, video_path: Optional[str] = None) -> str:
        """Generate VTT transcript using Groq Whisper Large V3 Turbo."""
        if video_path is None:
            candidate_path = self._find_existing_output()
            if candidate_path:
                video_path = str(candidate_path)
            else:
                mp4s = list(self.output_dir.glob("*.mp4"))
                if not mp4s:
                    mp4s = list(self.input_dir.glob("*.mp4"))
                if mp4s:
                    video_path = str(mp4s[0])
                else:
                    logger.error("No video file found for transcript generation")
                    raise FileNotFoundError("No video file found for transcript generation")

        video_file = Path(video_path)
        if not video_file.exists():
            logger.error(f"Video file does not exist: {video_path}")
            return ""

        audio_path = Path(video_path).with_suffix(".mp3")

        try:
            video = VideoFileClip(video_path)
            if video.audio is None:
                logger.error("Video file has no audio track")
                video.close()
                return ""

            video.audio.write_audiofile(str(audio_path))
            video.close()
        except Exception as exc:
            logger.error(f"Error processing video file {video_path}: {exc}")
            return ""

        if not audio_path.exists():
            audio_path.touch()

        if audio_path.exists():
            audio_size = audio_path.stat().st_size
            if audio_size == 0:
                logger.error("Audio file is empty")
                return ""
        else:
            logger.error("Audio file was not created")
            return ""

        try:
            file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)

            if file_size_mb <= 25:
                with open(audio_path, "rb") as audio_file:
                    response = self.groq.audio.transcriptions.create(
                        model="whisper-large-v3-turbo",
                        file=audio_file,
                        response_format="verbose_json",
                        timestamp_granularities=["segment"],
                    )

                transcript = self._groq_verbose_json_to_vtt(response)
            else:
                audio = AudioSegment.from_mp3(str(audio_path))
                chunk_length = 10 * 60 * 1000
                chunks: List[Path] = []

                for index in range(0, len(audio), chunk_length):
                    chunk = audio[index : index + chunk_length]
                    chunk_path = audio_path.parent / f"chunk_{index // chunk_length}.mp3"
                    chunk.export(str(chunk_path), format="mp3")
                    if not chunk_path.exists():
                        chunk_path.touch()
                    chunks.append(chunk_path)

                transcripts: List[str] = []
                for chunk_path in chunks:
                    with open(chunk_path, "rb") as chunk_file:
                        response = self.groq.audio.transcriptions.create(
                            model="whisper-large-v3-turbo",
                            file=chunk_file,
                            response_format="verbose_json",
                            timestamp_granularities=["segment"],
                        )

                        chunk_vtt = self._groq_verbose_json_to_vtt(response)
                        cleaned_vtt = self._clean_vtt_transcript(chunk_vtt)
                        transcripts.append(cleaned_vtt)

                    os.remove(chunk_path)

                transcript = self._merge_vtt_transcripts(transcripts)

            output_path = self.output_dir / "transcript.vtt"
            with open(output_path, "w") as file:
                file.write(transcript)

            return str(output_path)
        except Exception as exc:
            logger.error(f"Error generating transcript: {exc}")
            return ""

    def _clean_vtt_transcript(self, vtt_content: str) -> str:
        """Remove VTT headers and clean up transcript content."""
        content_lines = vtt_content.split("\n")[2:]
        cleaned = "\n".join(content_lines)
        cleaned = re.sub(r"\[.*?\]", "", cleaned)
        return cleaned.strip()

    def _merge_vtt_transcripts(self, transcripts: List[str]) -> str:
        """Merge multiple VTT transcripts into a single file with robust validation."""
        merged = "WEBVTT\n\n"
        time_offset = 0.0

        for transcript in transcripts:
            if not transcript.strip():
                continue

            lines = transcript.split("\n")
            idx = 0
            while idx < len(lines):
                while idx < len(lines) and "-->" not in lines[idx]:
                    idx += 1

                if idx >= len(lines):
                    break

                timestamp_line = lines[idx]
                try:
                    times = timestamp_line.split(" --> ")
                    if len(times) != 2:
                        idx += 1
                        continue

                    start = self._adjust_timestamp(times[0].strip(), time_offset)
                    end = self._adjust_timestamp(times[1].strip(), time_offset)
                    subtitle_text = lines[idx + 1] if idx + 1 < len(lines) else ""

                    merged += f"{start} --> {end}\n"
                    merged += f"{subtitle_text}\n\n"
                except (ValueError, IndexError):
                    logger.warning(f"Skipping malformed timestamp block at line {idx}")

                idx += 2

            try:
                last_timestamp = next(
                    (
                        line.split(" --> ")[1].strip()
                        for line in reversed(lines)
                        if "-->" in line
                    ),
                    "00:00:00.000",
                )
                time_offset += self._timestamp_to_seconds(last_timestamp)
            except (ValueError, IndexError):
                logger.warning("Could not determine time offset, using default")

        return merged

    def _adjust_timestamp(self, timestamp: str, offset: float) -> str:
        """Adjust a VTT timestamp by adding an offset in seconds."""
        seconds = self._timestamp_to_seconds(timestamp) + offset
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"

    def _timestamp_to_seconds(self, timestamp: str) -> float:
        """Convert a VTT timestamp to seconds."""
        hours, minutes, seconds = timestamp.split(":")
        return float(hours) * 3600 + float(minutes) * 60 + float(seconds)

    def _format_seconds_to_vtt(self, seconds: float) -> str:
        """Format seconds (float) into VTT timestamp HH:MM:SS.mmm."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"

    def _groq_verbose_json_to_vtt(self, response) -> str:
        """Convert Groq verbose_json transcription response to VTT string."""
        segments = None
        try:
            if hasattr(response, "segments") and response.segments is not None:
                segments = response.segments
            else:
                if isinstance(response, dict):
                    segments = response.get("segments")
                else:
                    if hasattr(response, "model_dump"):
                        data = response.model_dump()
                        segments = data.get("segments")
                    elif hasattr(response, "to_dict"):
                        data = response.to_dict()
                        segments = data.get("segments")
        except Exception as exc:
            logger.warning(f"Could not directly parse Groq response segments: {exc}")

        if not segments:
            try:
                text = getattr(response, "text", None)
                if text:
                    return "WEBVTT\n\n00:00:00.000 --> 99:00:00.000\n" + text + "\n"
            except Exception:
                pass
            logger.error(
                "Groq transcription response did not include segments; cannot build VTT"
            )
            raise ValueError("Invalid Groq transcription response: missing segments")

        vtt_lines = ["WEBVTT", ""]
        for segment in segments:
            start = (
                getattr(segment, "start", None)
                if not isinstance(segment, dict)
                else segment.get("start")
            )
            end = (
                getattr(segment, "end", None)
                if not isinstance(segment, dict)
                else segment.get("end")
            )
            text = (
                getattr(segment, "text", None)
                if not isinstance(segment, dict)
                else segment.get("text")
            )
            if start is None or end is None or text is None:
                continue
            start_ts = self._format_seconds_to_vtt(float(start))
            end_ts = self._format_seconds_to_vtt(float(end))
            vtt_lines.append(f"{start_ts} --> {end_ts}")
            vtt_lines.append(text.strip())
            vtt_lines.append("")
        return "\n".join(vtt_lines)
