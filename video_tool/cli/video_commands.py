"""Video processing commands: concat, timestamps, transcript, silence-removal, download."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Optional

import typer

from video_tool import VideoProcessor
from video_tool.cli import validate_ai_env_vars, video_app
from video_tool.ui import (
    ask_confirm,
    ask_path,
    ask_text,
    ask_choice,
    console,
    normalize_path,
    status_spinner,
    step_complete,
    step_error,
    step_start,
    step_warning,
)
from video_tool.video_processor.constants import SUPPORTED_VIDEO_SUFFIXES

SUPPORTED_VIDEO_LABEL = ", ".join(ext.lstrip(".").upper() for ext in SUPPORTED_VIDEO_SUFFIXES)


@video_app.command("download")
def download(
    url: Optional[str] = typer.Option(None, "--url", "-u", help="Video URL to download"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o", help="Output directory"),
    name: Optional[str] = typer.Option(None, "--name", "-n", help="Output filename"),
) -> None:
    """Download video from URL (YouTube, etc.)."""
    if url is None:
        url = ask_text("Video URL", required=True)

    if output_dir is None:
        output_dir_str = ask_path("Output directory", required=True)
        output_dir = Path(output_dir_str)
    else:
        output_dir = Path(normalize_path(str(output_dir)))

    output_dir.mkdir(parents=True, exist_ok=True)

    filename = name
    if filename and not filename.endswith(".mp4"):
        filename += ".mp4"

    step_start("Downloading video", {"URL": url, "Output": str(output_dir)})
    if filename:
        console.print(f"  [dim]Filename:[/dim] {filename}")

    with status_spinner("Downloading"):
        processor = VideoProcessor(str(output_dir))
        processor.download_video(url, output_dir, filename)

    step_complete("Download complete")


@video_app.command("silence-removal")
def silence_removal(
    input_dir: Optional[Path] = typer.Option(None, "--input-dir", "-i", help="Input directory containing videos"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o", help="Output directory"),
) -> None:
    """Remove silences from videos."""
    if not validate_ai_env_vars():
        raise typer.Exit(1)

    if input_dir is None:
        input_dir_str = ask_path("Input directory (containing videos)", required=True)
        input_dir = Path(input_dir_str)
    else:
        input_dir = Path(normalize_path(str(input_dir)))

    if not input_dir.exists() or not input_dir.is_dir():
        step_error(f"Invalid input directory: {input_dir}")
        raise typer.Exit(1)

    output_dir_path = None
    if output_dir:
        output_dir_path = str(Path(normalize_path(str(output_dir))))

    step_start("Removing silences", {"Input": str(input_dir), "Output": output_dir_path or str(input_dir / "output")})

    with status_spinner("Processing"):
        processor = VideoProcessor(str(input_dir), output_dir=output_dir_path)
        processed_dir = processor.remove_silences()

    step_complete("Silence removal complete", processed_dir)


@video_app.command("concat")
def concat(
    input_dir: Optional[Path] = typer.Option(None, "--input-dir", "-i", help="Input directory containing videos"),
    output_path: Optional[Path] = typer.Option(None, "--output-path", "-o", help="Full output file path (.mp4)"),
    fast_concat: Optional[bool] = typer.Option(None, "--fast-concat/--no-fast-concat", "-f", help="Use fast concatenation (skip reprocessing)"),
) -> None:
    """Concatenate videos into a single file."""
    if not validate_ai_env_vars():
        raise typer.Exit(1)

    if input_dir is None:
        input_dir_str = ask_path("Input directory (containing videos to concatenate)", required=True)
        input_dir = Path(input_dir_str)
    else:
        input_dir = Path(normalize_path(str(input_dir)))

    if not input_dir.exists() or not input_dir.is_dir():
        step_error(f"Invalid input directory: {input_dir}")
        raise typer.Exit(1)

    # Resolve output path (relative paths resolve to input_dir)
    if output_path:
        final_output_path = Path(normalize_path(str(output_path)))
        if not final_output_path.is_absolute():
            final_output_path = input_dir / final_output_path
        if final_output_path.suffix.lower() != ".mp4":
            final_output_path = final_output_path.with_suffix(".mp4")
    else:
        # Interactive: prompt for path, auto-generate if empty
        output_path_str = ask_path("Output file path (.mp4, defaults to input dir)", required=False)
        if output_path_str:
            final_output_path = Path(output_path_str)
            if not final_output_path.is_absolute():
                final_output_path = input_dir / final_output_path
            if final_output_path.suffix.lower() != ".mp4":
                final_output_path = final_output_path.with_suffix(".mp4")
        else:
            # Auto-generate with timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            final_output_path = input_dir / "output" / f"concat_{timestamp}.mp4"

    output_dir_path = final_output_path.parent
    video_title = final_output_path.stem  # Derive title from filename

    # Prompt for fast concat if not specified
    use_fast_concat = fast_concat
    if use_fast_concat is None:
        use_fast_concat = ask_confirm("Use fast concatenation?", default=False)

    processor = VideoProcessor(str(input_dir), video_title=video_title, output_dir=str(output_dir_path))

    step_start(
        "Concatenating videos",
        {"Input": str(input_dir), "Output": str(final_output_path), "Fast mode": "Yes" if use_fast_concat else "No"},
    )

    with status_spinner("Processing"):
        output_video = processor.concatenate_videos(
            skip_reprocessing=use_fast_concat, output_path=str(final_output_path)
        )

    if not output_video:
        step_error("Concatenation did not produce an output file")
        raise typer.Exit(1)

    step_complete("Concatenation complete", output_video)

    # Write metadata
    _write_concat_metadata(processor, Path(output_video), use_fast_concat)


def _write_concat_metadata(processor: VideoProcessor, output_video_path: Path, fast_concat: bool) -> None:
    """Write metadata.json for concatenated video."""
    metadata_path = output_video_path.with_name("metadata.json")

    creation_date, detected_title, duration_minutes = processor._get_video_metadata(str(output_video_path))

    metadata = {
        "output_path": str(output_video_path),
        "output_directory": str(output_video_path.parent),
        "output_filename": output_video_path.name,
        "concat_mode": "fast" if fast_concat else "standard",
    }

    if creation_date:
        metadata["created_at"] = creation_date
    if detected_title:
        metadata["detected_title"] = detected_title
    if duration_minutes is not None:
        metadata["duration_minutes"] = duration_minutes
        metadata["duration_seconds"] = round(duration_minutes * 60, 2)

    try:
        metadata["file_size_bytes"] = output_video_path.stat().st_size
    except OSError:
        pass

    # Merge with existing metadata
    existing = _read_metadata(metadata_path)
    merged = {**existing, **metadata} if existing else metadata

    _write_metadata(metadata_path, merged)


@video_app.command("timestamps")
def timestamps(
    input_dir: Optional[Path] = typer.Option(None, "--input-dir", "-i", help="Input directory or video file path"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o", help="Output directory"),
    output_path: Optional[Path] = typer.Option(None, "--output-path", help="Full path for output JSON"),
    stamps_from_transcript: Optional[str] = typer.Option(
        None, "--stamps-from-transcript", help="Generate from transcript (optionally provide path)"
    ),
    stamps_from_clips: bool = typer.Option(False, "--stamps-from-clips", help="Generate from clip boundaries"),
    granularity: Optional[str] = typer.Option(None, "--granularity", "-g", help="Granularity (low/medium/high)"),
    timestamp_notes: Optional[str] = typer.Option(None, "--timestamp-notes", help="Additional instructions"),
) -> None:
    """Generate timestamps/chapters for videos."""
    if not validate_ai_env_vars():
        raise typer.Exit(1)

    if input_dir is None:
        input_dir_str = ask_path("Input directory or video file path", required=True)
        input_dir = Path(input_dir_str)
    else:
        input_dir = Path(normalize_path(str(input_dir)))

    if not input_dir.exists():
        step_error(f"Invalid input path: {input_dir}")
        raise typer.Exit(1)

    is_video_input = input_dir.is_file()
    if is_video_input and input_dir.suffix.lower() not in SUPPORTED_VIDEO_SUFFIXES:
        step_error(f"Input file must be one of ({SUPPORTED_VIDEO_LABEL}): {input_dir}")
        raise typer.Exit(1)

    base_dir = input_dir.parent if is_video_input else input_dir
    output_dir_path = Path(normalize_path(str(output_dir))) if output_dir else base_dir / "output"
    final_output_path = str(Path(normalize_path(str(output_path)))) if output_path else str(output_dir_path / "timestamps.json")

    # Determine timestamp generation mode
    use_transcript = False
    transcript_path = None

    if is_video_input:
        use_transcript = True
        if stamps_from_transcript:
            transcript_path = normalize_path(stamps_from_transcript)
            if not Path(transcript_path).exists():
                step_warning(f"Transcript not found at {transcript_path}. Will auto-generate.")
                transcript_path = None
    elif stamps_from_clips:
        use_transcript = False
    elif stamps_from_transcript is not None:
        use_transcript = True
        if stamps_from_transcript:
            transcript_path = normalize_path(stamps_from_transcript)
            if not Path(transcript_path).exists():
                step_warning(f"Transcript not found at {transcript_path}. Will auto-generate.")
                transcript_path = None
    else:
        # Interactive: ask user preference
        per_clip = ask_confirm("Generate one chapter per clip?", default=True)
        use_transcript = not per_clip
        if use_transcript:
            transcript_input = ask_path("Path to transcript (leave blank to auto-generate)", required=False)
            if transcript_input:
                transcript_path = transcript_input

    # Handle granularity for transcript-based timestamps
    final_granularity = granularity.lower() if granularity else "medium"
    if use_transcript and final_granularity not in {"low", "medium", "high"}:
        step_warning("Invalid granularity; defaulting to 'medium'")
        final_granularity = "medium"

    step_start("Generating timestamps", {"Input": str(input_dir), "Output": final_output_path})

    with status_spinner("Analyzing"):
        processor = VideoProcessor(str(base_dir), output_dir=str(output_dir_path))
        timestamps_info = processor.generate_timestamps(
            output_path=final_output_path,
            transcript_path=transcript_path,
            stamps_from_transcript=use_transcript,
            granularity=final_granularity,
            timestamp_notes=timestamp_notes,
            video_path=str(input_dir) if is_video_input else None,
        )

    step_complete("Timestamps generated", final_output_path)

    # Update metadata
    _update_timestamps_metadata(final_output_path, timestamps_info, use_transcript)


def _update_timestamps_metadata(output_path: str, timestamps_info: dict, use_transcript: bool) -> None:
    """Update metadata.json with timestamps info."""
    metadata_path = Path(output_path).parent / "metadata.json"
    timestamps_payload = timestamps_info.get("timestamps", []) if isinstance(timestamps_info, dict) else []

    existing = _read_metadata(metadata_path) or {}
    existing["timestamps"] = timestamps_payload
    _write_metadata(metadata_path, existing)


@video_app.command("transcript")
def transcript(
    video_path: Optional[Path] = typer.Option(None, "--video-path", "-v", help="Path to video file"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o", help="Output directory"),
    output_path: Optional[Path] = typer.Option(None, "--output-path", help="Full path for output VTT"),
) -> None:
    """Generate transcript for a video using Whisper."""
    if not validate_ai_env_vars():
        raise typer.Exit(1)

    if video_path is None:
        video_path_str = ask_path("Path to video file", required=True)
        video_path = Path(video_path_str)
    else:
        video_path = Path(normalize_path(str(video_path)))

    if not video_path.exists() or not video_path.is_file():
        step_error(f"Invalid video file: {video_path}")
        raise typer.Exit(1)

    output_dir_path = Path(normalize_path(str(output_dir))) if output_dir else video_path.parent / "output"
    final_output_path = str(Path(normalize_path(str(output_path)))) if output_path else str(output_dir_path / "transcript.vtt")

    step_start("Generating transcript", {"Video": str(video_path), "Output": final_output_path})

    with status_spinner("Transcribing"):
        processor = VideoProcessor(str(video_path.parent), output_dir=str(output_dir_path))
        transcript_result = processor.generate_transcript(str(video_path), output_path=final_output_path)

    step_complete("Transcript generated", transcript_result)

    # Update metadata
    _update_transcript_metadata(transcript_result)


def _update_transcript_metadata(transcript_path: str) -> None:
    """Update metadata.json with transcript info."""
    transcript_file = Path(transcript_path)
    metadata_path = transcript_file.parent / "metadata.json"

    try:
        transcript_content = transcript_file.read_text(encoding="utf-8")
    except OSError:
        return

    existing = _read_metadata(metadata_path) or {}
    existing["transcript"] = transcript_content
    existing["transcript_format"] = transcript_file.suffix.lstrip(".").lower()
    _write_metadata(metadata_path, existing)


# --- Metadata helpers ---


def _read_metadata(path: Path) -> Optional[dict]:
    """Read metadata.json if it exists."""
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _write_metadata(path: Path, data: dict) -> None:
    """Write metadata.json."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        console.print(f"  [dim]Metadata:[/dim] {path}")
    except OSError as e:
        step_warning(f"Unable to write metadata: {e}")
