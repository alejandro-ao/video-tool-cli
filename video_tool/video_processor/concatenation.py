from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from textwrap import dedent
from typing import Dict, List, Optional, Sequence, Tuple

from pydantic import BaseModel

from .shared import VideoFileClip, logger


class ChapterUpdate(BaseModel):
    start: str
    end: str
    title: str


class ChapterUpdateResponse(BaseModel):
    chapters: List[ChapterUpdate]


class TranscriptChapter(BaseModel):
    start: str
    title: str


class TranscriptChapterResponse(BaseModel):
    chapters: List[TranscriptChapter]


CHAPTER_SYSTEM_PROMPT = dedent(
    """
    You generate polished YouTube chapter titles.
    Match each chapter's start and end timestamp exactly as provided.
    Titles must be concise, descriptive, and reflect the transcript excerpt.
    Return structured data using the supplied schema only.
    """
).strip()

TRANSCRIPT_CHAPTER_SYSTEM_PROMPT = dedent(
    """
    You design YouTube chapter lists directly from timecoded transcripts.
    Keep chapters ordered, evenly spaced, and limited to the key inflection points.
    Format start times as H:MM:SS with zero-padded hours.
    Start the first chapter at 0:00 with an intro title.
    Return structured data using the provided schema only.
    """
).strip()

DEFAULT_TRANSCRIPT_CHAPTER_PROMPT = dedent(
    """
    Generate YouTube chapters for the video "{video_title}".

    Requirements:
    - Use the transcript timeline below to anchor start times.
    - Start with "0:00" for the intro.
    - Keep 4-12 chapters with medium granularity (not every sentence, not overly broad).
    - Ensure times stay within the video duration ({video_duration}).
    - Titles should be concise, specific, and action-oriented.

    Transcript timeline:
    {transcript}
    """
).strip()


class ConcatenationMixin:
    """Video concatenation, timestamp generation, and encoding utilities."""

    def concatenate_videos(
        self,
        output_filename: Optional[str] = None,
        skip_reprocessing: bool = False,
        output_path: Optional[str] = None,
    ) -> str:
        """Concatenate multiple MP4 videos in alphabetical order using ffmpeg."""
        processed_dir = self.input_dir / "processed"
        mp4_files: List[Path] = []

        if processed_dir.exists():
            try:
                mp4_files = self.get_mp4_files(str(processed_dir))
                logger.info(f"Using videos from processed directory: {processed_dir}")
            except ValueError:
                pass

        if not mp4_files:
            mp4_files = self.get_mp4_files()
            logger.info(f"Using videos from input directory: {self.input_dir}")

        if not mp4_files:
            logger.error(
                f"No MP4 files found in either the processed directory ({processed_dir}) "
                f"or input directory ({self.input_dir})"
            )
            return ""

        logger.info(f"Found {len(mp4_files)} MP4 files to concatenate")

        # Determine output path
        if output_path:
            resolved_output_path = Path(output_path)
        else:
            output_filename = self._determine_output_filename(output_filename)
            resolved_output_path = self._resolve_unique_output_path(output_filename)

        resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_dir = self.input_dir / "temp_processed"
        temp_dir.mkdir(exist_ok=True)

        try:
            if skip_reprocessing:
                logger.info("Fast concatenation mode: skipping video reprocessing")
                concat_list = temp_dir / "concat_list.txt"
                with open(concat_list, "w") as file:
                    for mp4_file in mp4_files:
                        file.write(f"file '{mp4_file.resolve()}'\n")

                logger.info("Concatenating videos without reprocessing")
                subprocess.run(
                    [
                        "ffmpeg",
                        "-f",
                        "concat",
                        "-safe",
                        "0",
                        "-i",
                        str(concat_list),
                        "-c",
                        "copy",
                        str(resolved_output_path),
                    ],
                    check=True,
                    **self._quiet_subprocess_kwargs(),
                )
            else:
                logger.info(
                    "Standard concatenation mode: reprocessing videos for compatibility"
                )

                probe_cmd = [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=width,height,r_frame_rate,codec_name",
                    "-of",
                    "json",
                    str(mp4_files[0]),
                ]
                probe_result = subprocess.run(
                    probe_cmd, capture_output=True, text=True, check=True
                )
                video_info = json.loads(probe_result.stdout)
                stream_info = video_info["streams"][0]

                audio_probe_cmd = [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "a:0",
                    "-show_entries",
                    "stream=codec_name,sample_rate,channels",
                    "-of",
                    "json",
                    str(mp4_files[0]),
                ]
                audio_result = subprocess.run(
                    audio_probe_cmd, capture_output=True, text=True, check=True
                )
                audio_info = json.loads(audio_result.stdout)
                audio_stream = audio_info["streams"][0] if audio_info["streams"] else None

                processed_files: List[Path] = []
                for mp4_file in mp4_files:
                    output_file = temp_dir / f"processed_{mp4_file.name}"
                    numerator, denominator = stream_info["r_frame_rate"].split("/")
                    fps = float(int(numerator) / int(denominator))

                    cmd = [
                        "ffmpeg",
                        "-hwaccel",
                        "auto",
                        "-i",
                        str(mp4_file),
                        "-c:v",
                        "h264_videotoolbox"
                        if stream_info["codec_name"] == "h264"
                        else stream_info["codec_name"],
                        "-s",
                        f"{stream_info['width']}x{stream_info['height']}",
                        "-r",
                        str(fps),
                        "-preset",
                        "fast",
                        "-profile:v",
                        "high",
                    ]

                    if audio_stream:
                        cmd.extend(
                            [
                                "-c:a",
                                audio_stream["codec_name"],
                                "-ar",
                                audio_stream["sample_rate"],
                                "-ac",
                                str(audio_stream["channels"]),
                            ]
                        )

                    cmd.extend(["-y", str(output_file)])
                    logger.info(
                        f"Standardizing video with hardware acceleration: {mp4_file.name}"
                    )
                    subprocess.run(
                        cmd,
                        check=True,
                        **self._quiet_subprocess_kwargs(),
                    )
                    processed_files.append(output_file)

                concat_list = temp_dir / "concat_list.txt"
                with open(concat_list, "w") as file:
                    for processed_file in processed_files:
                        file.write(f"file '{processed_file.name}'\n")

                logger.info("Concatenating standardized videos")
                subprocess.run(
                    [
                        "ffmpeg",
                        "-f",
                        "concat",
                        "-safe",
                        "0",
                        "-i",
                        str(concat_list),
                        "-c",
                        "copy",
                        str(resolved_output_path),
                    ],
                    check=True,
                    **self._quiet_subprocess_kwargs(),
                )

            self.last_output_path = resolved_output_path
            return str(resolved_output_path)
        except subprocess.CalledProcessError as exc:
            logger.error(f"Error during video processing: {exc}")
            if exc.stderr:
                logger.error(f"FFmpeg stderr: {exc.stderr}")
            raise
        finally:
            if temp_dir.exists():
                for temp_file in temp_dir.glob("*"):
                    temp_file.unlink()
                temp_dir.rmdir()

    def generate_timestamps(
        self,
        output_path: Optional[str] = None,
        transcript_path: Optional[str] = None,
        stamps_from_transcript: bool = False,
    ) -> Dict:
        """Generate timestamp information for the video with chapters based on input videos or transcript."""
        resolved_output_path = (
            Path(output_path).expanduser() if output_path else self.output_dir / "timestamps.json"
        )

        if stamps_from_transcript:
            transcript_file, transcript_generated = self._resolve_transcript_for_timestamps(
                transcript_path
            )

            if transcript_file:
                try:
                    timestamps = self._generate_timestamps_from_transcript_file(transcript_file)
                    video_info = {
                        "timestamps": timestamps,
                        "metadata": {
                            "creation_date": datetime.now().isoformat(),
                            "chapter_source": "transcript",
                            "transcript_path": str(transcript_file),
                            "transcript_generated": transcript_generated,
                        },
                    }
                    resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(resolved_output_path, "w") as file:
                        json.dump([video_info], file, indent=2)
                    return video_info
                except Exception as exc:
                    logger.warning(
                        f"Transcript-driven timestamp generation failed: {exc}. Falling back to clip-based chapters."
                    )
            else:
                logger.warning(
                    "Transcript-driven timestamps requested but no transcript was provided or generated. "
                    "Falling back to clip-based chapters."
                )

        processed_dir = self.input_dir / "processed"
        mp4_files: List[Path] = []

        if processed_dir.exists():
            try:
                mp4_files = self.get_mp4_files(str(processed_dir))
                logger.info(
                    f"Generating timestamps from processed directory: {processed_dir}"
                )
            except ValueError:
                pass

        if not mp4_files:
            mp4_files = self.get_mp4_files()
            if callable(getattr(logger, "__call__", None)):
                logger("Generating timestamps from input directory")
            logger.info(f"Generating timestamps from input directory: {self.input_dir}")

        if not mp4_files:
            logger.warning(
                f"No MP4 files found in either the processed directory ({processed_dir}) "
                f"or input directory ({self.input_dir})"
            )
            video_info = {
                "timestamps": [],
                "metadata": {
                    "creation_date": datetime.now().isoformat(),
                },
            }
            resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(resolved_output_path, "w") as file:
                json.dump([video_info], file, indent=2)
            return video_info

        timestamps = []
        current_time = 0

        for mp4_file in mp4_files:
            duration = None
            try:
                meta = self._get_video_metadata(str(mp4_file))
                if isinstance(meta, dict):
                    duration = int(meta.get("duration", 0)) if meta.get("duration") else None
                elif isinstance(meta, tuple) and len(meta) == 3 and meta[2] is not None:
                    duration = int(meta[2] * 60)
            except Exception as exc:
                logger.debug(f"Metadata extraction failed for {mp4_file}: {exc}")

            if duration is None:
                if callable(getattr(logger, "__call__", None)):
                    logger(f"Metadata unavailable for {mp4_file}, attempting MoviePy fallback")
                logger.warning(f"Falling back to MoviePy for duration of {mp4_file}")
                try:
                    with self.suppress_external_output():
                        try:
                            with VideoFileClip(str(mp4_file), audio=False, verbose=False) as video:  # type: ignore[arg-type]
                                duration = int(video.duration)
                        except TypeError:
                            with VideoFileClip(str(mp4_file), audio=False) as video:
                                duration = int(video.duration)
                except Exception as exc:
                    if callable(getattr(logger, "__call__", None)):
                        logger(f"Failed to extract duration for {mp4_file}: {exc}")
                    logger.error(f"Failed to extract duration for {mp4_file}: {exc}")
                    continue

            start_time = current_time
            end_time = current_time + duration

            timestamps.append(
                {
                    "start": f"{start_time//3600:02d}:{(start_time%3600)//60:02d}:{start_time%60:02d}",
                    "end": f"{end_time//3600:02d}:{(end_time%3600)//60:02d}:{end_time%60:02d}",
                    "title": mp4_file.stem,
                }
            )

            current_time = end_time

        transcript_path = self.output_dir / "transcript.vtt"
        if transcript_path.exists():
            try:
                transcript_segments = self._load_transcript_segments(transcript_path)
                if transcript_segments:
                    timestamps = self._refine_timestamp_titles_with_structured_output(
                        timestamps, transcript_segments
                    )
            except Exception as exc:
                logger.warning(f"Unable to refine timestamp titles via transcript: {exc}")

        video_info = {
            "timestamps": timestamps,
            "metadata": {
                "creation_date": datetime.now().isoformat(),
                "chapter_source": "clip-durations",
            },
        }

        resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(resolved_output_path, "w") as file:
            json.dump([video_info], file, indent=2)

        return video_info

    def _resolve_transcript_for_timestamps(
        self, transcript_path: Optional[str]
    ) -> Tuple[Optional[Path], bool]:
        """Resolve or generate a transcript for transcript-driven timestamp creation."""
        if transcript_path:
            candidate = Path(transcript_path).expanduser()
            if candidate.exists():
                logger.info(f"Using provided transcript for timestamps: {candidate}")
                return candidate, False
            logger.warning(f"Provided transcript not found at {candidate}, attempting to generate one.")

        default_transcript = self.output_dir / "transcript.vtt"
        if default_transcript.exists():
            logger.info(f"Using existing transcript for timestamps: {default_transcript}")
            return default_transcript, False

        logger.info("No transcript supplied; generating transcript on the fly for timestamps.")
        generated_path = self.generate_transcript(output_path=str(default_transcript))
        if generated_path:
            candidate = Path(generated_path)
            if candidate.exists():
                return candidate, True

        logger.warning("Transcript generation failed; cannot generate timestamps from transcript.")
        return None, False

    def _generate_timestamps_from_transcript_file(self, transcript_file: Path) -> List[Dict[str, str]]:
        """Generate chapters by prompting against a transcript timeline."""
        segments = self._load_transcript_segments(transcript_file)
        if not segments:
            raise ValueError("Transcript contained no segments for timestamp generation.")

        transcript_timeline = self._build_transcript_timeline_for_prompt(segments)
        try:
            video_duration_seconds = max(
                float(segment["end"]) for segment in segments if segment.get("end") is not None
            )
        except ValueError:
            video_duration_seconds = max(float(segment.get("start", 0)) for segment in segments)
        chapter_response = self._request_chapters_from_transcript_timeline(
            transcript_timeline=transcript_timeline,
            video_duration=self._format_seconds_as_hms(video_duration_seconds),
        )

        if not chapter_response or not getattr(chapter_response, "chapters", None):
            raise ValueError("No chapters were returned from the transcript-driven prompt.")

        ordered_chapters: List[Tuple[float, str]] = []
        for chapter in chapter_response.chapters:
            try:
                start_seconds = self._parse_vtt_timestamp(
                    self._normalize_timestamp_for_seconds(chapter.start)
                )
            except Exception as exc:
                logger.warning(f"Skipping chapter with unparsable start '{chapter.start}': {exc}")
                continue

            title = chapter.title.strip() if isinstance(chapter.title, str) else ""
            ordered_chapters.append((start_seconds, title or "Chapter"))

        if not ordered_chapters:
            raise ValueError("Structured chapter response did not include usable chapters.")

        ordered_chapters.sort(key=lambda item: item[0])

        deduped_chapters: List[Tuple[float, str]] = []
        last_start: Optional[float] = None
        for start_seconds, title in ordered_chapters:
            if last_start is not None and start_seconds <= last_start:
                logger.warning(
                    f"Skipping out-of-order or duplicate chapter start ({start_seconds}) after {last_start}."
                )
                continue
            deduped_chapters.append((start_seconds, title))
            last_start = start_seconds

        timestamps: List[Dict[str, str]] = []
        for index, (start_seconds, title) in enumerate(deduped_chapters):
            next_start = (
                deduped_chapters[index + 1][0]
                if index + 1 < len(deduped_chapters)
                else video_duration_seconds
            )

            if next_start < start_seconds:
                logger.warning(
                    f"Chapter start time {start_seconds} is after next chapter start {next_start}; skipping."
                )
                continue

            timestamps.append(
                {
                    "start": self._format_seconds_as_hms(start_seconds),
                    "end": self._format_seconds_as_hms(next_start),
                    "title": title,
                }
            )

        if not timestamps:
            raise ValueError("Transcript-driven timestamps could not be constructed from chapter data.")

        return timestamps

    def _build_transcript_timeline_for_prompt(
        self, segments: List[Dict[str, object]], max_chars: int = 12000
    ) -> str:
        """Flatten transcript segments into a prompt-friendly timeline."""
        lines: List[str] = []
        for segment in segments:
            start = float(segment.get("start", 0))
            text = str(segment.get("text", "")).strip()
            if not text:
                continue
            lines.append(f"{self._format_seconds_as_hms(start)} — {text}")

        combined = "\n".join(lines)
        if len(combined) > max_chars:
            combined = combined[:max_chars] + "\n..."
        return combined

    def _request_chapters_from_transcript_timeline(
        self,
        *,
        transcript_timeline: str,
        video_duration: str,
    ) -> Optional[TranscriptChapterResponse]:
        prompt_template = self.prompts.get(
            "generate-timestamps-from-transcript",
            DEFAULT_TRANSCRIPT_CHAPTER_PROMPT,
        )

        user_prompt = prompt_template.format(
            transcript=transcript_timeline,
            video_title=self.video_title or self.input_dir.name,
            video_duration=video_duration,
        )

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": TRANSCRIPT_CHAPTER_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ]

        try:
            return self._invoke_openai_chat_structured_output(
                model="gpt-4o-mini",
                messages=messages,
                schema=TranscriptChapterResponse,
                temperature=0.35,
                max_tokens=550,
            )
        except Exception as exc:
            logger.warning(f"Transcript chapter request failed: {exc}")
            return None

    def _format_seconds_as_hms(self, seconds: float) -> str:
        """Format seconds into HH:MM:SS (zero-padded)."""
        total_seconds = max(0, int(seconds))
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        secs = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    def _parse_vtt_timestamp(self, timestamp: str) -> float:
        """Convert a VTT timestamp (HH:MM:SS.mmm) to seconds."""
        try:
            hours, minutes, seconds = timestamp.strip().split(":")
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        except ValueError as exc:
            raise ValueError(f"Invalid VTT timestamp: {timestamp}") from exc

    def _normalize_timestamp_for_seconds(self, timestamp: str) -> str:
        """Ensure timestamps include hours and milliseconds for parsing."""
        normalized = timestamp.strip()
        if normalized.count(":") == 1:
            normalized = f"00:{normalized}"
        if "." not in normalized:
            normalized = f"{normalized}.000"
        return normalized

    def _load_transcript_segments(self, transcript_path: Path) -> List[Dict[str, object]]:
        """Parse a VTT transcript into time-bound text segments."""
        try:
            content = transcript_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            logger.warning(f"Transcript not found for timestamp enrichment: {transcript_path}")
            return []

        lines = content.splitlines()
        segments: List[Dict[str, object]] = []
        index = 0
        total_lines = len(lines)

        while index < total_lines:
            line = lines[index].strip()
            if "-->" not in line:
                index += 1
                continue

            try:
                start_str, end_str = [part.strip() for part in line.split("-->")]
                start_seconds = self._parse_vtt_timestamp(self._normalize_timestamp_for_seconds(start_str))
                end_seconds = self._parse_vtt_timestamp(self._normalize_timestamp_for_seconds(end_str))
            except ValueError:
                index += 1
                continue

            index += 1
            text_lines: List[str] = []
            while index < total_lines:
                text_line = lines[index].strip()
                if not text_line:
                    break
                text_lines.append(text_line)
                index += 1

            if text_lines:
                segments.append(
                    {
                        "start": start_seconds,
                        "end": end_seconds,
                        "text": " ".join(text_lines),
                    }
                )

            index += 1

        return segments

    def _refine_timestamp_titles_with_structured_output(
        self,
        timestamps: List[Dict[str, str]],
        transcript_segments: List[Dict[str, object]],
    ) -> List[Dict[str, str]]:
        """Use structured output to enrich chapter titles with transcript context."""
        if not timestamps:
            return timestamps

        class ChapterUpdate(BaseModel):
            start: str
            end: str
            title: str

        class ChapterUpdateResponse(BaseModel):
            chapters: List[ChapterUpdate]

        chapter_contexts: List[Dict[str, str]] = []
        context_char_limit = 600
        for entry in timestamps:
            start_seconds = self._parse_vtt_timestamp(
                self._normalize_timestamp_for_seconds(entry["start"])
            )
            end_seconds = self._parse_vtt_timestamp(
                self._normalize_timestamp_for_seconds(entry["end"])
            )

            excerpts: List[str] = []
            for segment in transcript_segments:
                segment_start = float(segment["start"])
                segment_end = float(segment["end"])
                if segment_end >= start_seconds and segment_start <= end_seconds:
                    segment_text = str(segment.get("text", "")).strip()
                    if segment_text:
                        excerpts.append(segment_text)

            context_text = " ".join(excerpts).strip()
            if not context_text:
                context_text = "No transcript context captured for this interval."

            if len(context_text) > context_char_limit:
                context_text = context_text[:context_char_limit]

            chapter_contexts.append(
                {
                    "start": entry["start"],
                    "end": entry["end"],
                    "current_title": entry.get("title", ""),
                    "transcript_excerpt": context_text,
                }
            )

        updated_titles: Dict[Tuple[str, str], str] = {}
        batch_size = 4
        for index in range(0, len(chapter_contexts), batch_size):
            chunk = chapter_contexts[index : index + batch_size]
            response = self._request_structured_chapter_updates(chunk)

            if response is None and len(chunk) > 1:
                for item in chunk:
                    fallback_response = self._request_structured_chapter_updates([item])
                    if fallback_response:
                        for chapter in fallback_response.chapters:
                            key = (chapter.start.strip(), chapter.end.strip())
                            if chapter.title.strip():
                                updated_titles[key] = chapter.title.strip()
                continue

            if response:
                for chapter in response.chapters:
                    if chapter.title.strip():
                        key = (chapter.start.strip(), chapter.end.strip())
                        updated_titles[key] = chapter.title.strip()

        if updated_titles:
            for entry in timestamps:
                key = (entry["start"].strip(), entry["end"].strip())
                new_title = updated_titles.get(key)
                if new_title:
                    entry["title"] = new_title

        return timestamps

    def _request_structured_chapter_updates(
        self, chapter_contexts: Sequence[Dict[str, str]]
    ) -> Optional[ChapterUpdateResponse]:
        if not chapter_contexts:
            return None

        payload = {
            "video_title": self.video_title or Path(self.input_dir).stem,
            "chapters": list(chapter_contexts),
            "instructions": "Generate clear, descriptive chapter titles using the provided transcript excerpts. Keep titles under 70 characters and make them engaging.",
        }

        messages: List[Dict[str, str]] = [
            {"role": "system", "content": CHAPTER_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ]

        try:
            structured_response = self._invoke_openai_chat_structured_output(
                model="gpt-4o-mini",
                messages=messages,
                schema=ChapterUpdateResponse,
                temperature=0.3,
                max_tokens=256,
            )
            return structured_response
        except Exception as exc:
            logger.warning(
                f"Structured chapter generation failed for batch of size {len(chapter_contexts)}: {exc}"
            )
            return None

    def match_video_encoding(
        self,
        source_video_path: str,
        reference_video_path: str,
        output_filename: Optional[str] = None,
    ) -> str:
        """Re-encode source video to match the encoding parameters of the reference video."""
        source_path = Path(source_video_path)
        reference_path = Path(reference_video_path)

        if not source_path.exists():
            raise ValueError(f"Source video does not exist: {source_path}")
        if not reference_path.exists():
            raise ValueError(f"Reference video does not exist: {reference_path}")

        logger.info(
            f"Re-encoding {source_path.name} to match encoding of {reference_path.name}"
        )

        video_probe_cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,r_frame_rate,codec_name,bit_rate,pix_fmt,profile,level",
            "-of",
            "json",
            str(reference_path),
        ]
        video_result = subprocess.run(
            video_probe_cmd, capture_output=True, text=True, check=True
        )
        video_info = json.loads(video_result.stdout)
        video_stream = video_info["streams"][0]

        audio_probe_cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_name,sample_rate,channels,bit_rate",
            "-of",
            "json",
            str(reference_path),
        ]
        audio_result = subprocess.run(
            audio_probe_cmd, capture_output=True, text=True, check=True
        )
        audio_info = json.loads(audio_result.stdout)
        audio_stream = audio_info["streams"][0] if audio_info["streams"] else None

        fps_fraction = video_stream["r_frame_rate"].split("/")
        fps = float(int(fps_fraction[0]) / int(fps_fraction[1]))

        if not output_filename:
            source_stem = source_path.stem
            reference_stem = reference_path.stem
            output_filename = f"{source_stem}_reencoded_to_match_{reference_stem}.mp4"

        output_path = source_path.parent / output_filename

        cmd = [
            "ffmpeg",
            "-hwaccel",
            "auto",
            "-i",
            str(source_path),
            "-y",
        ]

        video_codec = video_stream["codec_name"]
        if video_codec == "h264":
            cmd.extend(["-c:v", "h264_videotoolbox"])
        elif video_codec == "hevc":
            cmd.extend(["-c:v", "hevc_videotoolbox"])
        else:
            cmd.extend(["-c:v", video_codec])

        cmd.extend(
            [
                "-s",
                f"{video_stream['width']}x{video_stream['height']}",
                "-r",
                str(fps),
            ]
        )

        if "bit_rate" in video_stream and video_stream["bit_rate"] != "N/A":
            bitrate_kbps = int(int(video_stream["bit_rate"]) / 1000)
            cmd.extend(
                [
                    "-b:v",
                    f"{bitrate_kbps}k",
                    "-maxrate",
                    f"{int(bitrate_kbps * 1.5)}k",
                    "-bufsize",
                    f"{int(bitrate_kbps * 2)}k",
                ]
            )

        if audio_stream:
            cmd.extend(
                [
                    "-c:a",
                    audio_stream["codec_name"],
                    "-ar",
                    audio_stream["sample_rate"],
                    "-ac",
                    str(audio_stream["channels"]),
                ]
            )
            if "bit_rate" in audio_stream and audio_stream["bit_rate"] != "N/A":
                audio_bitrate_kbps = int(int(audio_stream["bit_rate"]) / 1000)
                cmd.extend(["-b:a", f"{audio_bitrate_kbps}k"])
        else:
            cmd.extend(["-an"])

        cmd.append(str(resolved_output_path))

        logger.info(
            f"Re-encoding {source_path.name} with parameters from {reference_path.name}"
        )
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info(f"Successfully re-encoded video to {output_path}")
            return str(resolved_output_path)
        except subprocess.CalledProcessError as exc:
            logger.error(f"Failed to re-encode {source_path.name}")
            logger.error(f"FFmpeg command: {' '.join(cmd)}")
            logger.error(f"FFmpeg stderr: {exc.stderr}")
            raise

    def compress_video(
        self,
        input_path: str,
        output_filename: Optional[str] = None,
        codec: str = "h265",
        crf: int = 23,
        preset: str = "medium",
    ) -> str:
        """Compress an MP4 video to reduce file size while maintaining quality."""
        input_file = Path(input_path)
        if not input_file.exists():
            raise ValueError(f"Input video does not exist: {input_file}")

        logger.info(f"Compressing video: {input_file.name}")
        original_size_mb = input_file.stat().st_size / (1024 * 1024)
        logger.info(f"Original file size: {original_size_mb:.2f} MB")

        if not output_filename:
            stem = input_file.stem
            suffix = input_file.suffix
            output_filename = f"{stem}_compressed{suffix}"

        output_path = input_file.parent / output_filename

        if codec == "auto":
            try:
                test_cmd = [
                    "ffmpeg",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc=duration=1:size=320x240:rate=1",
                    "-c:v",
                    "hevc_videotoolbox",
                    "-t",
                    "1",
                    "-f",
                    "null",
                    "-",
                ]
                subprocess.run(test_cmd, capture_output=True, check=True)
                codec = "h265"
                logger.info("Using H.265 (HEVC) codec for optimal compression")
            except subprocess.CalledProcessError:
                codec = "h264"
                logger.info("H.265 not available, using H.264 codec")

        if codec == "h265":
            video_encoder = "hevc_videotoolbox"
            fallback_encoder = "libx265"
        else:
            video_encoder = "h264_videotoolbox"
            fallback_encoder = "libx264"

        cmd = [
            "ffmpeg",
            "-i",
            str(input_file),
            "-y",
        ]

        try:
            test_cmd = [
                "ffmpeg",
                "-f",
                "lavfi",
                "-i",
                "testsrc=duration=1:size=320x240:rate=1",
                "-c:v",
                video_encoder,
                "-t",
                "1",
                "-f",
                "null",
                "-",
            ]
            subprocess.run(test_cmd, capture_output=True, check=True)

            cmd.extend(["-c:v", video_encoder])
            if codec == "h265":
                cmd.extend(
                    [
                        "-q:v",
                        str(crf),
                        "-profile:v",
                        "main",
                        "-tag:v",
                        "hvc1",
                    ]
                )
            else:
                cmd.extend(
                    [
                        "-q:v",
                        str(crf),
                        "-profile:v",
                        "high",
                    ]
                )

            logger.info(f"Using hardware encoder: {video_encoder}")
        except subprocess.CalledProcessError:
            cmd.extend(["-c:v", fallback_encoder])
            cmd.extend(["-crf", str(crf), "-preset", preset])
            if codec == "h265":
                cmd.extend(["-profile:v", "main", "-tag:v", "hvc1"])
            else:
                cmd.extend(["-profile:v", "high"])

            logger.info(f"Using software encoder: {fallback_encoder}")

        cmd.extend(
            [
                "-c:a",
                "copy",
                "-avoid_negative_ts",
                "make_zero",
                "-movflags",
                "+faststart",
            ]
        )

        cmd.extend(["-map_metadata", "-1"])
        cmd.append(str(resolved_output_path))

        logger.info(f"Compressing with codec: {codec}, CRF: {crf}, preset: {preset}")
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")

        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            compressed_size_mb = output_path.stat().st_size / (1024 * 1024)
            compression_ratio = (1 - compressed_size_mb / original_size_mb) * 100

            logger.info("Compression completed successfully!")
            logger.info(f"Original size: {original_size_mb:.2f} MB")
            logger.info(f"Compressed size: {compressed_size_mb:.2f} MB")
            logger.info(f"Size reduction: {compression_ratio:.1f}%")

            return str(resolved_output_path)
        except subprocess.CalledProcessError as exc:
            logger.error(f"Failed to compress video: {input_file.name}")
            logger.error(f"FFmpeg command: {' '.join(cmd)}")
            logger.error(f"FFmpeg stderr: {exc.stderr}")

            if output_path.exists():
                output_path.unlink()

            raise
