"""Deployment commands: bunny-upload, bunny-transcript, bunny-chapters."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Sequence, cast

import typer

from video_tool import VideoProcessor
from video_tool.cli import validate_bunny_env_vars, deploy_app
from video_tool.ui import (
    ask_path,
    ask_text,
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


def _resolve_bunny_credentials(
    library_id: Optional[str] = None,
    access_key: Optional[str] = None,
) -> tuple[str, str]:
    """Resolve Bunny credentials from args/env and prompt if missing."""
    library = (library_id or os.getenv("BUNNY_LIBRARY_ID") or "").strip()
    access = (access_key or os.getenv("BUNNY_ACCESS_KEY") or "").strip()

    if not library:
        library = ask_text("Bunny Library ID", required=True) or ""
    if not access:
        access = ask_text("Bunny Access Key", required=True) or ""

    return library, access


@deploy_app.command("bunny-upload")
def bunny_upload(
    video_path: Optional[Path] = typer.Option(None, "--video-path", "-v", help="Path to video file to upload"),
    batch_dir: Optional[Path] = typer.Option(None, "--batch-dir", "-b", help="Directory of videos to upload"),
    metadata_path: Optional[Path] = typer.Option(None, "--metadata-path", "-m", help="Path to metadata.json"),
    bunny_library_id: Optional[str] = typer.Option(None, "--bunny-library-id", help="Bunny.net library ID"),
    bunny_access_key: Optional[str] = typer.Option(None, "--bunny-access-key", help="Bunny.net access key"),
    bunny_collection_id: Optional[str] = typer.Option(None, "--bunny-collection-id", help="Bunny.net collection ID"),
) -> None:
    """Upload video(s) to Bunny.net CDN."""
    if video_path and batch_dir:
        step_error("Provide either --video-path or --batch-dir, not both")
        raise typer.Exit(1)

    # Resolve batch directory
    batch_path: Optional[Path] = None
    if batch_dir:
        batch_path = Path(normalize_path(str(batch_dir)))
        if not batch_path.exists() or not batch_path.is_dir():
            step_error(f"Invalid batch directory: {batch_dir}")
            raise typer.Exit(1)

    # Resolve single video
    video_file: Optional[Path] = None
    if video_path:
        video_file = Path(normalize_path(str(video_path)))
    elif not batch_dir:
        video_path_str = ask_path("Path to video file to upload", required=True)
        video_file = Path(video_path_str)

    if video_file and (not video_file.exists() or not video_file.is_file()):
        step_error(f"Invalid video file: {video_file}")
        raise typer.Exit(1)

    # Resolve metadata path
    if batch_path:
        default_metadata = batch_path / "output" / "metadata.json"
    elif video_file:
        default_metadata = video_file.parent / "output" / "metadata.json"
    else:
        default_metadata = Path.cwd() / "metadata.json"

    meta_path = Path(normalize_path(str(metadata_path))) if metadata_path else default_metadata

    # Get credentials
    library_id, access_key = _resolve_bunny_credentials(bunny_library_id, bunny_access_key)
    collection_id = (bunny_collection_id or os.getenv("BUNNY_COLLECTION_ID") or "").strip() or None

    # Batch upload
    if batch_path:
        _upload_batch(batch_path, meta_path, library_id, access_key, collection_id)
        return

    # Single upload
    _upload_single(video_file, meta_path, library_id, access_key, collection_id)


def _upload_batch(
    batch_path: Path,
    metadata_path: Path,
    library_id: str,
    access_key: str,
    collection_id: Optional[str],
) -> None:
    """Upload multiple videos from a directory."""
    step_start("Uploading videos to Bunny.net", {"Directory": str(batch_path), "Library ID": library_id})

    processor = VideoProcessor(str(batch_path))
    try:
        video_files = processor.get_video_files(str(batch_path))
    except Exception as e:
        step_error(f"Unable to read directory: {e}")
        raise typer.Exit(1)

    if not video_files:
        step_error(f"No supported video files found in {batch_path}")
        raise typer.Exit(1)

    successes: List[tuple[str, str]] = []
    failures: List[str] = []

    for file_path in video_files:
        console.print(f"  [cyan]Uploading {file_path.name}...[/cyan]")
        try:
            result = processor.upload_bunny_video(
                video_path=str(file_path),
                library_id=library_id,
                access_key=access_key,
                collection_id=collection_id,
            )
            if result:
                video_id = result.get("video_id", "")
                successes.append((file_path.name, video_id))
                console.print(f"    [green]Uploaded[/green] (ID: {video_id})")
            else:
                failures.append(file_path.name)
                console.print(f"    [red]Failed[/red]")
        except Exception as e:
            failures.append(file_path.name)
            console.print(f"    [red]Error: {e}[/red]")

    if not successes:
        step_error("All uploads failed")
        raise typer.Exit(1)

    if failures:
        step_warning(f"Some uploads failed: {', '.join(failures)}")
    else:
        step_complete("All videos uploaded successfully")

    # Update metadata
    existing = _read_metadata(metadata_path) or {}
    existing["bunny_batch_uploads"] = [
        {"file": name, "video_id": vid, "library_id": library_id, "collection_id": collection_id}
        for name, vid in successes
    ]
    _write_metadata(metadata_path, existing)


def _upload_single(
    video_file: Path,
    metadata_path: Path,
    library_id: str,
    access_key: str,
    collection_id: Optional[str],
) -> None:
    """Upload a single video."""
    step_start("Uploading video to Bunny.net", {"Video": str(video_file), "Library ID": library_id})

    with status_spinner("Uploading"):
        processor = VideoProcessor(str(video_file.parent))
        result = processor.upload_bunny_video(
            video_path=str(video_file),
            library_id=library_id,
            access_key=access_key,
            collection_id=collection_id,
        )

    if result:
        video_id = result.get("video_id", "")
        step_complete(f"Video uploaded (ID: {video_id})")

        # Update metadata
        existing = _read_metadata(metadata_path) or {}
        existing["bunny_video"] = {
            "video_id": video_id,
            "library_id": library_id,
            "collection_id": collection_id,
            "file": video_file.name,
        }
        _write_metadata(metadata_path, existing)
    else:
        step_error("Failed to upload video to Bunny.net")
        raise typer.Exit(1)


@deploy_app.command("bunny-transcript")
def bunny_transcript(
    video_id: Optional[str] = typer.Option(None, "--video-id", "-v", help="Bunny.net video ID"),
    transcript_path: Optional[Path] = typer.Option(None, "--transcript-path", "-t", help="Path to transcript (.vtt)"),
    language: str = typer.Option("en", "--language", "-l", help="Caption language code"),
    bunny_library_id: Optional[str] = typer.Option(None, "--bunny-library-id", help="Bunny.net library ID"),
    bunny_access_key: Optional[str] = typer.Option(None, "--bunny-access-key", help="Bunny.net access key"),
) -> None:
    """Upload transcript captions to a Bunny.net video."""
    # Resolve video ID
    vid_id = video_id or os.getenv("BUNNY_VIDEO_ID")
    if not vid_id:
        vid_id = ask_text("Bunny Video ID", required=True)

    # Resolve credentials
    library_id, access_key = _resolve_bunny_credentials(bunny_library_id, bunny_access_key)

    # Resolve transcript
    if transcript_path:
        transcript_file = Path(normalize_path(str(transcript_path)))
    else:
        transcript_path_str = ask_path("Path to transcript file (.vtt)", required=True)
        transcript_file = Path(transcript_path_str)

    if not transcript_file.exists() or not transcript_file.is_file():
        step_error(f"Invalid transcript file: {transcript_file}")
        raise typer.Exit(1)

    lang = (language or os.getenv("BUNNY_CAPTION_LANGUAGE") or "en").strip()

    step_start(
        "Uploading transcript to Bunny.net",
        {"Transcript": str(transcript_file), "Video ID": vid_id, "Language": lang},
    )

    with status_spinner("Uploading"):
        processor = VideoProcessor(str(transcript_file.parent), output_dir=str(transcript_file.parent))
        success = processor.update_bunny_transcript(
            video_id=vid_id,
            library_id=library_id,
            access_key=access_key,
            transcript_path=str(transcript_file),
            language=lang,
        )

    if success:
        step_complete("Captions uploaded to Bunny.net")
    else:
        step_error("Failed to upload transcript to Bunny.net")
        raise typer.Exit(1)


@deploy_app.command("bunny-chapters")
def bunny_chapters(
    video_id: Optional[str] = typer.Option(None, "--video-id", "-v", help="Bunny.net video ID"),
    chapters_path: Optional[Path] = typer.Option(None, "--chapters-path", "-c", help="Path to chapters JSON"),
    bunny_library_id: Optional[str] = typer.Option(None, "--bunny-library-id", help="Bunny.net library ID"),
    bunny_access_key: Optional[str] = typer.Option(None, "--bunny-access-key", help="Bunny.net access key"),
) -> None:
    """Upload chapter metadata to a Bunny.net video."""
    # Resolve video ID
    vid_id = video_id or os.getenv("BUNNY_VIDEO_ID")
    if not vid_id:
        vid_id = ask_text("Bunny Video ID", required=True)

    # Resolve credentials
    library_id, access_key = _resolve_bunny_credentials(bunny_library_id, bunny_access_key)

    # Resolve chapters file
    if chapters_path:
        chapters_file = Path(normalize_path(str(chapters_path)))
    else:
        chapters_path_str = ask_path("Path to chapters JSON file", required=True)
        chapters_file = Path(chapters_path_str)

    if not chapters_file.exists() or not chapters_file.is_file():
        step_error(f"Invalid chapters file: {chapters_file}")
        raise typer.Exit(1)

    # Load chapters
    try:
        with open(chapters_file, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        step_error(f"Unable to read chapters file: {e}")
        raise typer.Exit(1)

    chapters_payload = _coerce_chapters(raw_data)
    if not chapters_payload:
        step_error("Unable to determine chapter structure from file")
        raise typer.Exit(1)

    step_start("Uploading chapters to Bunny.net", {"Chapters file": str(chapters_file), "Video ID": vid_id})

    with status_spinner("Uploading"):
        processor = VideoProcessor(str(chapters_file.parent))
        success = processor.update_bunny_chapters(
            video_id=vid_id,
            library_id=library_id,
            access_key=access_key,
            chapters=chapters_payload,
        )

    if success:
        step_complete("Chapters uploaded to Bunny.net")
    else:
        step_error("Failed to upload chapters to Bunny.net")
        raise typer.Exit(1)


def _coerce_chapters(data: object) -> Optional[List[Dict[str, str]]]:
    """Extract chapters from various JSON structures."""

    def _collect_dicts(items: Sequence[object]) -> List[Dict[str, str]]:
        return [cast(Dict[str, str], item) for item in items if isinstance(item, dict)]

    if isinstance(data, list):
        if data and isinstance(data[0], dict) and "timestamps" in data[0]:
            timestamps = data[0].get("timestamps")
            if isinstance(timestamps, list):
                return _collect_dicts(timestamps) or None
            return None
        return _collect_dicts(data) or None

    if isinstance(data, dict):
        for key in ("chapters", "timestamps"):
            value = data.get(key)
            if isinstance(value, list):
                return _collect_dicts(value) or None
        if all(key in data for key in ("title", "start", "end")):
            return [cast(Dict[str, str], data)]

    return None


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
