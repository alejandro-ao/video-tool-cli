"""Video processing commands: concat, timestamps, transcript, silence-removal, download, extract-audio, enhance-audio."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

import requests
import typer

from video_tool import VideoProcessor
from video_tool.cli import validate_ai_env_vars, video_app
from video_tool.config import get_llm_config
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
from video_tool.video_processor.constants import SUPPORTED_VIDEO_SUFFIXES, SUPPORTED_AUDIO_SUFFIXES

SUPPORTED_VIDEO_LABEL = ", ".join(ext.lstrip(".").upper() for ext in SUPPORTED_VIDEO_SUFFIXES)
SUPPORTED_AUDIO_LABEL = ", ".join(ext.lstrip(".").upper() for ext in SUPPORTED_AUDIO_SUFFIXES)


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
    input_path: Optional[Path] = typer.Option(None, "--input", "-i", help="Input video file"),
    output_path: Optional[Path] = typer.Option(None, "--output-path", "-o", help="Output video file path"),
    threshold: float = typer.Option(1.0, "--threshold", "-t", help="Min silence duration in seconds to remove"),
) -> None:
    """Remove silences from a video file."""
    if input_path is None:
        input_path_str = ask_path("Input video file", required=True)
        input_path = Path(input_path_str)
    else:
        input_path = Path(normalize_path(str(input_path)))

    if not input_path.exists() or not input_path.is_file():
        step_error(f"Invalid input file: {input_path}")
        raise typer.Exit(1)

    # Resolve output path
    if output_path:
        final_output_path = Path(normalize_path(str(output_path)))
        if not final_output_path.is_absolute():
            final_output_path = input_path.parent / final_output_path
    else:
        # Interactive: prompt for path, auto-generate if empty
        default_output = f"{input_path.stem}_no_silence.mp4"
        output_path_str = ask_path(f"Output file path (defaults to {default_output})", required=False)
        if output_path_str:
            final_output_path = Path(output_path_str)
            if not final_output_path.is_absolute():
                final_output_path = input_path.parent / final_output_path
        else:
            final_output_path = input_path.parent / default_output

    if final_output_path.suffix.lower() != ".mp4":
        final_output_path = final_output_path.with_suffix(".mp4")

    step_start("Removing silences", {
        "Input": str(input_path),
        "Output": str(final_output_path),
        "Threshold": f"{threshold}s"
    })

    with status_spinner("Processing"):
        processor = VideoProcessor(str(input_path.parent))
        result = processor.remove_silence_from_video(
            video_path=str(input_path),
            output_path=str(final_output_path),
            min_silence_len=int(threshold * 1000)
        )

    step_complete("Silence removal complete", result)


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
    mode: Optional[str] = typer.Option(None, "--mode", "-m", help="Generation mode: 'clips' or 'transcript'"),
    input_path: Optional[Path] = typer.Option(None, "--input", "-i", help="Input directory (clips) or VTT file (transcript)"),
    output_path: Optional[Path] = typer.Option(None, "--output-path", "-o", help="Output JSON file path"),
    granularity: Optional[str] = typer.Option(None, "--granularity", "-g", help="Granularity: low/medium/high (transcript mode)"),
    notes: Optional[str] = typer.Option(None, "--notes", "-n", help="Additional LLM instructions (transcript mode)"),
) -> None:
    """Generate video chapter timestamps."""
    # 1. Determine mode (interactive or flag)
    if mode is None:
        console.print("  [dim]clips[/dim] = 1 chapter per clip, [dim]transcript[/dim] = LLM-analyzed VTT")
        mode = ask_choice("How do you want to generate timestamps?", ["clips", "transcript"])

    mode = mode.lower()
    if mode not in ("clips", "transcript"):
        step_error(f"Invalid mode: {mode}. Must be 'clips' or 'transcript'")
        raise typer.Exit(1)

    # 2. Validate AI env only for transcript mode
    if mode == "transcript" and not validate_ai_env_vars():
        raise typer.Exit(1)

    # 3. Get input path
    if input_path is None:
        if mode == "clips":
            input_path_str = ask_path("Directory containing video clips", required=True)
        else:
            input_path_str = ask_path("Path to VTT transcript file", required=True)
        input_path = Path(input_path_str)
    else:
        input_path = Path(normalize_path(str(input_path)))

    # 4. Validate input
    if mode == "clips":
        if not input_path.exists() or not input_path.is_dir():
            step_error(f"Invalid directory: {input_path}")
            raise typer.Exit(1)
        base_dir = input_path
    else:  # transcript
        if not input_path.exists() or not input_path.is_file():
            step_error(f"Invalid VTT file: {input_path}")
            raise typer.Exit(1)
        if input_path.suffix.lower() != ".vtt":
            step_warning(f"Expected .vtt file, got: {input_path.suffix}")
        base_dir = input_path.parent

    # 5. Resolve output path
    if output_path:
        final_output_path = Path(normalize_path(str(output_path)))
        if not final_output_path.is_absolute():
            final_output_path = base_dir / final_output_path
    else:
        output_path_str = ask_path("Output JSON path (defaults to timestamps.json)", required=False)
        if output_path_str:
            final_output_path = Path(output_path_str)
            if not final_output_path.is_absolute():
                final_output_path = base_dir / final_output_path
        else:
            final_output_path = base_dir / "timestamps.json"

    if final_output_path.suffix.lower() != ".json":
        final_output_path = final_output_path.with_suffix(".json")

    # 6. Get granularity (transcript mode only)
    final_granularity = "medium"
    if mode == "transcript":
        if granularity:
            final_granularity = granularity.lower()
        else:
            console.print("  [dim]low[/dim] = fewer chapters, [dim]medium[/dim] = balanced, [dim]high[/dim] = more chapters")
            final_granularity = ask_choice("Granularity level", ["low", "medium", "high"], default="medium")

        if final_granularity not in ("low", "medium", "high"):
            step_warning(f"Invalid granularity '{final_granularity}', using 'medium'")
            final_granularity = "medium"

    # 7. Generate timestamps
    step_info = {
        "Mode": mode,
        "Input": str(input_path),
        "Output": str(final_output_path),
    }
    if mode == "transcript":
        step_info["Granularity"] = final_granularity
        llm_config = get_llm_config("timestamps")
        step_info["Model"] = llm_config.model
        step_info["Provider"] = llm_config.base_url
    step_start("Generating timestamps", step_info)

    with status_spinner("Processing"):
        processor = VideoProcessor(str(base_dir), output_dir=str(final_output_path.parent))
        timestamps_info = processor.generate_timestamps(
            output_path=str(final_output_path),
            transcript_path=str(input_path) if mode == "transcript" else None,
            stamps_from_transcript=(mode == "transcript"),
            granularity=final_granularity,
            timestamp_notes=notes,
        )

    step_complete("Timestamps generated", str(final_output_path))
    _update_timestamps_metadata(str(final_output_path), timestamps_info, mode == "transcript")


def _update_timestamps_metadata(output_path: str, timestamps_info: dict, use_transcript: bool) -> None:
    """Update metadata.json with timestamps info."""
    metadata_path = Path(output_path).parent / "metadata.json"
    timestamps_payload = timestamps_info.get("timestamps", []) if isinstance(timestamps_info, dict) else []

    existing = _read_metadata(metadata_path) or {}
    existing["timestamps"] = timestamps_payload
    _write_metadata(metadata_path, existing)


@video_app.command("transcript")
def transcript(
    input_path: Optional[Path] = typer.Option(None, "--input", "-i", help="Input video or audio file"),
    output_path: Optional[Path] = typer.Option(None, "--output-path", "-o", help="Output VTT file path"),
) -> None:
    """Generate VTT transcript from video or audio using Whisper."""
    if not validate_ai_env_vars():
        raise typer.Exit(1)

    # 1. Get input path
    if input_path is None:
        input_path_str = ask_path("Path to video or audio file", required=True)
        input_path = Path(input_path_str)
    else:
        input_path = Path(normalize_path(str(input_path)))

    # 2. Validate input
    if not input_path.exists() or not input_path.is_file():
        step_error(f"Invalid file: {input_path}")
        raise typer.Exit(1)

    suffix = input_path.suffix.lower()
    is_audio = suffix in SUPPORTED_AUDIO_SUFFIXES
    is_video = suffix in SUPPORTED_VIDEO_SUFFIXES

    if not is_audio and not is_video:
        step_error(f"Unsupported format: {suffix}. Use video ({SUPPORTED_VIDEO_LABEL}) or audio ({SUPPORTED_AUDIO_LABEL})")
        raise typer.Exit(1)

    base_dir = input_path.parent

    # 3. Resolve output path
    if output_path:
        final_output_path = Path(normalize_path(str(output_path)))
        if not final_output_path.is_absolute():
            final_output_path = base_dir / final_output_path
    else:
        output_path_str = ask_path("Output VTT path (defaults to transcript.vtt)", required=False)
        if output_path_str:
            final_output_path = Path(output_path_str)
            if not final_output_path.is_absolute():
                final_output_path = base_dir / final_output_path
        else:
            final_output_path = base_dir / "transcript.vtt"

    if final_output_path.suffix.lower() != ".vtt":
        final_output_path = final_output_path.with_suffix(".vtt")

    # 4. Generate transcript
    step_start("Generating transcript", {
        "Input": str(input_path),
        "Type": "audio" if is_audio else "video",
        "Output": str(final_output_path),
    })

    with status_spinner("Transcribing"):
        processor = VideoProcessor(str(base_dir), output_dir=str(final_output_path.parent))
        transcript_result = processor.generate_transcript(
            video_path=str(input_path),
            output_path=str(final_output_path),
        )

    step_complete("Transcript generated", transcript_result)
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


@video_app.command("extract-audio")
def extract_audio(
    input_path: Optional[Path] = typer.Option(None, "--input", "-i", help="Input video file"),
    output_path: Optional[Path] = typer.Option(None, "--output", "-o", help="Output MP3 file path"),
) -> None:
    """Extract audio from a video file to MP3."""
    from moviepy.video.io.VideoFileClip import VideoFileClip

    # 1. Get input path
    if input_path is None:
        input_path_str = ask_path("Path to video file", required=True)
        input_path = Path(input_path_str)
    else:
        input_path = Path(normalize_path(str(input_path)))

    # 2. Validate input
    if not input_path.exists() or not input_path.is_file():
        step_error(f"Invalid file: {input_path}")
        raise typer.Exit(1)

    suffix = input_path.suffix.lower()
    if suffix not in SUPPORTED_VIDEO_SUFFIXES:
        step_error(f"Unsupported format: {suffix}. Use video ({SUPPORTED_VIDEO_LABEL})")
        raise typer.Exit(1)

    # 3. Resolve output path
    if output_path:
        final_output_path = Path(normalize_path(str(output_path)))
        if not final_output_path.is_absolute():
            final_output_path = input_path.parent / final_output_path
    else:
        default_output = f"{input_path.stem}.mp3"
        output_path_str = ask_path(f"Output MP3 path (defaults to {default_output})", required=False)
        if output_path_str:
            final_output_path = Path(output_path_str)
            if not final_output_path.is_absolute():
                final_output_path = input_path.parent / final_output_path
        else:
            final_output_path = input_path.parent / default_output

    if final_output_path.suffix.lower() != ".mp3":
        final_output_path = final_output_path.with_suffix(".mp3")

    # Ensure output directory exists
    final_output_path.parent.mkdir(parents=True, exist_ok=True)

    # 4. Extract audio
    step_start("Extracting audio", {
        "Input": str(input_path),
        "Output": str(final_output_path),
    })

    with status_spinner("Processing"):
        try:
            with VideoFileClip(str(input_path)) as video:
                if video.audio is None:
                    step_error("Video has no audio track")
                    raise typer.Exit(1)
                video.audio.write_audiofile(str(final_output_path), logger=None)
        except typer.Exit:
            raise
        except Exception as exc:
            step_error(f"Failed to extract audio: {exc}")
            raise typer.Exit(1)

    step_complete("Audio extracted", str(final_output_path))


@video_app.command("enhance-audio")
def enhance_audio_cmd(
    input_path: Optional[Path] = typer.Option(None, "--input", "-i", help="Input video/audio file"),
    output_path: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
    denoise_only: bool = typer.Option(False, "--denoise-only", "-d", help="Only denoise, skip full enhancement"),
) -> None:
    """Enhance audio quality using Resemble AI (via Replicate)."""
    # 1. Check for API token
    api_token = os.environ.get("REPLICATE_API_TOKEN")
    if not api_token:
        step_error("REPLICATE_API_TOKEN environment variable not set")
        console.print("  [dim]Get a token at https://replicate.com/account/api-tokens[/dim]")
        raise typer.Exit(1)

    # 2. Get input path
    if input_path is None:
        input_path_str = ask_path("Path to video or audio file", required=True)
        input_path = Path(input_path_str)
    else:
        input_path = Path(normalize_path(str(input_path)))

    # 3. Validate input
    if not input_path.exists() or not input_path.is_file():
        step_error(f"Invalid file: {input_path}")
        raise typer.Exit(1)

    suffix = input_path.suffix.lower()
    is_audio = suffix in SUPPORTED_AUDIO_SUFFIXES
    is_video = suffix in SUPPORTED_VIDEO_SUFFIXES

    if not is_audio and not is_video:
        step_error(f"Unsupported format: {suffix}. Use video ({SUPPORTED_VIDEO_LABEL}) or audio ({SUPPORTED_AUDIO_LABEL})")
        raise typer.Exit(1)

    # 4. Resolve output path
    if output_path:
        final_output_path = Path(normalize_path(str(output_path)))
        if not final_output_path.is_absolute():
            final_output_path = input_path.parent / final_output_path
    else:
        default_output = f"{input_path.stem}_enhanced{input_path.suffix}"
        output_path_str = ask_path(f"Output path (defaults to {default_output})", required=False)
        if output_path_str:
            final_output_path = Path(output_path_str)
            if not final_output_path.is_absolute():
                final_output_path = input_path.parent / final_output_path
        else:
            final_output_path = input_path.parent / default_output

    # Ensure output has same extension as input
    if final_output_path.suffix.lower() != suffix:
        final_output_path = final_output_path.with_suffix(suffix)

    # Ensure output directory exists
    final_output_path.parent.mkdir(parents=True, exist_ok=True)

    # 5. Process
    step_start("Enhancing audio", {
        "Input": str(input_path),
        "Output": str(final_output_path),
        "Mode": "denoise only" if denoise_only else "full enhancement",
    })

    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            # Extract audio if video input
            if is_video:
                with status_spinner("Extracting audio from video"):
                    audio_path = temp_path / "audio.wav"
                    subprocess.run([
                        "ffmpeg", "-y", "-i", str(input_path),
                        "-vn", "-acodec", "pcm_s16le", "-ar", "44100", "-ac", "2",
                        str(audio_path)
                    ], check=True, capture_output=True)
            else:
                audio_path = input_path

            # Call Replicate API
            with status_spinner("Enhancing audio via Replicate (this may take a while)"):
                enhanced_url = _enhance_audio_replicate(audio_path, api_token, denoise_only)

            # Download enhanced audio
            with status_spinner("Downloading enhanced audio"):
                enhanced_audio_path = temp_path / "enhanced.wav"
                _download_file(enhanced_url, enhanced_audio_path)

            # Merge back or copy to output
            if is_video:
                with status_spinner("Merging enhanced audio with video"):
                    subprocess.run([
                        "ffmpeg", "-y",
                        "-i", str(input_path),
                        "-i", str(enhanced_audio_path),
                        "-c:v", "copy",
                        "-map", "0:v:0",
                        "-map", "1:a:0",
                        str(final_output_path)
                    ], check=True, capture_output=True)
            else:
                # Convert to original format
                with status_spinner("Converting to output format"):
                    subprocess.run([
                        "ffmpeg", "-y",
                        "-i", str(enhanced_audio_path),
                        str(final_output_path)
                    ], check=True, capture_output=True)

        step_complete("Audio enhancement complete", str(final_output_path))

    except subprocess.CalledProcessError as e:
        step_error(f"FFmpeg error: {e.stderr.decode() if e.stderr else str(e)}")
        raise typer.Exit(1)
    except Exception as e:
        step_error(f"Enhancement failed: {e}")
        raise typer.Exit(1)


def _enhance_audio_replicate(audio_path: Path, api_token: str, denoise_only: bool) -> str:
    """Call Replicate API to enhance audio. Returns URL to enhanced file."""
    import base64
    import time

    # Read and encode audio file
    with open(audio_path, "rb") as f:
        audio_data = base64.b64encode(f.read()).decode("utf-8")

    # Determine mime type
    suffix = audio_path.suffix.lower()
    mime_types = {
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".flac": "audio/flac",
        ".aac": "audio/aac",
        ".ogg": "audio/ogg",
    }
    mime_type = mime_types.get(suffix, "audio/wav")
    data_uri = f"data:{mime_type};base64,{audio_data}"

    # Create prediction
    headers = {
        "Authorization": f"Bearer {api_token}",
        "Content-Type": "application/json",
    }

    create_resp = requests.post(
        "https://api.replicate.com/v1/predictions",
        headers=headers,
        json={
            "version": "93266a7e7f5805fb79bcf213b1a4e0ef2e45aff3c06eefd96c59e850c87fd6a2",
            "input": {
                "input_audio": data_uri,
                "solver": "Midpoint",
                "number_function_evaluations": 64,
                "prior_temperature": 0.5,
                "denoise_flag": denoise_only,
            }
        },
        timeout=60,
    )
    create_resp.raise_for_status()
    prediction = create_resp.json()

    # Poll for completion (max 10 minutes)
    prediction_url = prediction["urls"]["get"]
    max_wait_seconds = 600
    start_time = time.monotonic()
    while prediction["status"] not in ("succeeded", "failed", "canceled"):
        if time.monotonic() - start_time > max_wait_seconds:
            raise RuntimeError(f"Replicate prediction timed out after {max_wait_seconds}s")
        time.sleep(2)
        poll_resp = requests.get(prediction_url, headers=headers, timeout=30)
        poll_resp.raise_for_status()
        prediction = poll_resp.json()

    if prediction["status"] != "succeeded":
        error = prediction.get("error", "Unknown error")
        raise RuntimeError(f"Replicate prediction failed: {error}")

    output = prediction["output"]
    if isinstance(output, list):
        return output[0]
    return output


def _download_file(url: str, dest: Path) -> None:
    """Download file from URL to destination path."""
    response = requests.get(url, stream=True, timeout=300)
    response.raise_for_status()
    with open(dest, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)


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
