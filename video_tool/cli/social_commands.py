"""Social posting commands for X and LinkedIn."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

import typer

from video_tool import VideoProcessor
from video_tool.cli import upload_app
from video_tool.config import get_credential
from video_tool.ui import (
    console,
    normalize_path,
    step_complete,
    step_error,
    step_start,
    step_warning,
)
from video_tool.video_processor.constants import SUPPORTED_VIDEO_SUFFIXES

SUPPORTED_VIDEO_LABEL = ", ".join(ext.lstrip(".").upper() for ext in SUPPORTED_VIDEO_SUFFIXES)


def _load_text(text: Optional[str], text_file: Optional[Path]) -> str:
    if text and text_file:
        step_error("Provide only one of --text or --text-file")
        raise typer.Exit(1)
    if not text and not text_file:
        step_error("Provide --text or --text-file")
        raise typer.Exit(1)

    if text_file:
        resolved = Path(normalize_path(str(text_file)))
        if not resolved.exists() or not resolved.is_file():
            step_error(f"Invalid text file: {resolved}")
            raise typer.Exit(1)
        try:
            return resolved.read_text(encoding="utf-8").strip()
        except OSError as exc:
            step_error(f"Unable to read text file: {exc}")
            raise typer.Exit(1)

    return (text or "").strip()


def _parse_thread_file(thread_file: Optional[Path]) -> List[str]:
    if not thread_file:
        return []

    resolved = Path(normalize_path(str(thread_file)))
    if not resolved.exists() or not resolved.is_file():
        step_error(f"Invalid thread file: {resolved}")
        raise typer.Exit(1)

    try:
        content = resolved.read_text(encoding="utf-8")
    except OSError as exc:
        step_error(f"Unable to read thread file: {exc}")
        raise typer.Exit(1)

    segments: List[str] = []
    buffer: List[str] = []
    for line in content.splitlines():
        if line.strip() == "---":
            segment = "\n".join(buffer).strip()
            if segment:
                segments.append(segment)
            buffer = []
            continue
        buffer.append(line)

    tail = "\n".join(buffer).strip()
    if tail:
        segments.append(tail)

    return segments


def _resolve_output_dir(output_dir: Optional[Path], video_path: Optional[Path]) -> Path:
    if output_dir:
        resolved = Path(normalize_path(str(output_dir)))
    elif video_path:
        resolved = Path(video_path).parent / "output"
    else:
        resolved = Path.cwd() / "output"

    resolved.mkdir(parents=True, exist_ok=True)
    return resolved


def _validate_video_path(video_path: Optional[Path]) -> Optional[Path]:
    if not video_path:
        return None

    resolved = Path(normalize_path(str(video_path)))
    if not resolved.exists() or not resolved.is_file():
        step_error(f"Invalid video file: {resolved}")
        raise typer.Exit(1)

    suffix = resolved.suffix.lower()
    if suffix not in SUPPORTED_VIDEO_SUFFIXES:
        step_error(f"Unsupported video format: {suffix}. Use: {SUPPORTED_VIDEO_LABEL}")
        raise typer.Exit(1)

    return resolved


def _append_url_to_text(text: str, url: Optional[str]) -> str:
    if not url:
        return text
    url_value = url.strip()
    if not url_value:
        return text
    if url_value in text:
        return text
    return f"{text.rstrip()}\n{url_value}"


def _warn_if_too_long(texts: List[str]) -> None:
    for idx, text in enumerate(texts, start=1):
        if len(text) > 280:
            step_warning(f"Thread item {idx} is {len(text)} characters (X limit is 280).")


def _read_metadata(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _write_metadata(path: Path, data: dict) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        console.print(f"  [dim]Metadata:[/dim] {path}")
    except OSError as exc:
        step_warning(f"Unable to write metadata: {exc}")


def _write_social_artifact(output_dir: Path, name: str, payload: dict) -> None:
    artifact_dir = output_dir / "social_posts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / name
    try:
        artifact_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        console.print(f"  [dim]Saved:[/dim] {artifact_path}")
    except OSError as exc:
        step_warning(f"Unable to write social artifact: {exc}")


@upload_app.command("twitter")
@upload_app.command("x")
def post_twitter(
    text: Optional[str] = typer.Option(None, "--text", help="Text for the first post"),
    text_file: Optional[Path] = typer.Option(None, "--text-file", help="Path to file with first post text"),
    thread_item: Optional[List[str]] = typer.Option(
        None,
        "--thread-item",
        help="Additional thread item text (repeatable)",
    ),
    thread_file: Optional[Path] = typer.Option(
        None,
        "--thread-file",
        help="Path to thread items file (--- delimiter)",
    ),
    video_path: Optional[Path] = typer.Option(None, "--video-path", help="Path to video to upload"),
    video_url: Optional[str] = typer.Option(None, "--video-url", help="Video URL to include"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", help="Output directory for metadata"),
    access_token: Optional[str] = typer.Option(None, "--access-token", help="X API bearer token"),
) -> None:
    """Post a thread to X (Twitter)."""
    primary_text = _load_text(text, text_file)
    thread_items: List[str] = []
    if thread_item:
        thread_items.extend([item for item in thread_item if item.strip()])
    thread_items.extend(_parse_thread_file(thread_file))

    thread = [primary_text] + thread_items
    thread[0] = _append_url_to_text(thread[0], video_url)

    _warn_if_too_long(thread)

    resolved_video = _validate_video_path(video_path)
    resolved_output_dir = _resolve_output_dir(output_dir, resolved_video)

    token = (access_token or get_credential("x_bearer_token") or "").strip()
    if not token:
        step_error("X API bearer token not configured. Run 'video-tool config keys'.")
        raise typer.Exit(1)

    step_warning("This will publish immediately to X (Twitter).")
    step_start("Posting to X", {"Thread items": str(len(thread)), "Video": str(resolved_video or "none")})

    processor = VideoProcessor(str(Path.cwd()), output_dir=str(resolved_output_dir))
    result = processor.post_x_thread(
        thread,
        access_token=token,
        video_path=str(resolved_video) if resolved_video else None,
    )

    if not result:
        step_error("Failed to post to X")
        raise typer.Exit(1)

    step_complete("Posted to X", result.get("primary_url"))

    metadata_path = resolved_output_dir / "metadata.json"
    existing = _read_metadata(metadata_path) or {}
    social = existing.get("social", {})
    social["x"] = result
    existing["social"] = social
    _write_metadata(metadata_path, existing)
    _write_social_artifact(resolved_output_dir, "x_post.json", result)


@upload_app.command("linkedin")
def post_linkedin(
    text: Optional[str] = typer.Option(None, "--text", help="Post text"),
    text_file: Optional[Path] = typer.Option(None, "--text-file", help="Path to file with post text"),
    video_path: Optional[Path] = typer.Option(None, "--video-path", help="Path to video to upload"),
    video_url: Optional[str] = typer.Option(None, "--video-url", help="Video URL to include"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", help="Output directory for metadata"),
    access_token: Optional[str] = typer.Option(None, "--access-token", help="LinkedIn access token"),
    author_urn: Optional[str] = typer.Option(None, "--author-urn", help="LinkedIn author URN"),
) -> None:
    """Publish a LinkedIn post."""
    body_text = _load_text(text, text_file)
    body_text = _append_url_to_text(body_text, video_url)

    resolved_video = _validate_video_path(video_path)
    resolved_output_dir = _resolve_output_dir(output_dir, resolved_video)

    token = (access_token or get_credential("linkedin_access_token") or "").strip()
    if not token:
        step_error("LinkedIn access token not configured. Run 'video-tool config keys'.")
        raise typer.Exit(1)

    author = (author_urn or get_credential("linkedin_author_urn") or "").strip()
    if not author:
        step_error("LinkedIn author URN not configured. Run 'video-tool config keys'.")
        raise typer.Exit(1)

    step_warning("This will publish immediately to LinkedIn.")
    step_start("Posting to LinkedIn", {"Video": str(resolved_video or "none")})

    processor = VideoProcessor(str(Path.cwd()), output_dir=str(resolved_output_dir))
    result = processor.post_linkedin_update(
        body_text,
        access_token=token,
        author_urn=author,
        video_path=str(resolved_video) if resolved_video else None,
    )

    if not result:
        step_error("Failed to post to LinkedIn")
        raise typer.Exit(1)

    step_complete("Posted to LinkedIn", result.get("post_url"))

    metadata_path = resolved_output_dir / "metadata.json"
    existing = _read_metadata(metadata_path) or {}
    social = existing.get("social", {})
    social["linkedin"] = result
    existing["social"] = social
    _write_metadata(metadata_path, existing)
    _write_social_artifact(resolved_output_dir, "linkedin_post.json", result)
