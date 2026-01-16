"""Content generation commands: description, seo, linkedin, twitter, context-cards, summary."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

import typer

from video_tool import VideoProcessor
from video_tool.cli import validate_ai_env_vars, content_app
from video_tool.ui import (
    ask_path,
    ask_text,
    ask_choice,
    ask_confirm,
    console,
    normalize_path,
    status_spinner,
    step_complete,
    step_error,
    step_start,
    step_warning,
)
from video_tool.config import ensure_config, get_links, prompt_links_setup
from video_tool.video_processor.constants import (
    SUPPORTED_VIDEO_SUFFIXES,
    SUPPORTED_AUDIO_SUFFIXES,
)

SUPPORTED_VIDEO_LABEL = ", ".join(ext.lstrip(".").upper() for ext in SUPPORTED_VIDEO_SUFFIXES)
SUPPORTED_AUDIO_LABEL = ", ".join(ext.lstrip(".").upper() for ext in SUPPORTED_AUDIO_SUFFIXES)
SUPPORTED_MEDIA_LABEL = f"{SUPPORTED_VIDEO_LABEL}, {SUPPORTED_AUDIO_LABEL}"
TRANSCRIPT_SUFFIXES = (".vtt", ".md", ".txt")


def _find_supported_videos(directory: Path) -> List[Path]:
    """Return supported video files within a directory, sorted by name."""
    videos: List[Path] = []
    for suffix in SUPPORTED_VIDEO_SUFFIXES:
        videos.extend(directory.glob(f"*{suffix}"))
    return sorted(videos)


@content_app.command("description")
def description(
    input_path: Optional[Path] = typer.Option(None, "--input", "-i", help="Input file (video/audio/vtt/md/txt)"),
    output_path: Optional[Path] = typer.Option(None, "--output-path", "-o", help="Full path for output description"),
    timestamps: Optional[Path] = typer.Option(None, "--timestamps", "-t", help="Path to timestamps JSON"),
    links: bool = typer.Option(False, "--links", "-l", help="Include persistent links from config"),
    code_link: Optional[str] = typer.Option(None, "--code-link", help="Link to code repository"),
    article_link: Optional[str] = typer.Option(None, "--article-link", help="Link to written article"),
) -> None:
    """Generate video description from transcript or media file."""
    if not validate_ai_env_vars():
        raise typer.Exit(1)

    # Ensure config exists (first-time setup if needed)
    ensure_config()

    transcript_file: Optional[Path] = None
    media_file: Optional[Path] = None
    transcript_generated = False

    # Resolve input
    if input_path is None:
        input_str = ask_path(f"Input file ({SUPPORTED_MEDIA_LABEL}, VTT, MD, TXT)", required=True)
        input_path = Path(input_str)
    else:
        input_path = Path(normalize_path(str(input_path)))

    if not input_path.exists() or not input_path.is_file():
        step_error(f"Invalid input file: {input_path}")
        raise typer.Exit(1)

    # Determine input type and handle accordingly
    suffix = input_path.suffix.lower()
    if suffix in TRANSCRIPT_SUFFIXES:
        # Use directly as transcript
        transcript_file = input_path
    elif suffix in SUPPORTED_VIDEO_SUFFIXES + SUPPORTED_AUDIO_SUFFIXES:
        # Transcribe first
        media_file = input_path
    else:
        step_error(f"Unsupported file type: {suffix}")
        raise typer.Exit(1)

    # Determine default output path
    default_output_path = input_path.parent / "description.md"

    # Ask for output path if not provided
    if output_path is None:
        output_str = ask_path(f"Output path (default: {default_output_path})", required=False)
        if output_str:
            output_path = Path(output_str)

    final_output_path = str(Path(normalize_path(str(output_path)))) if output_path else str(default_output_path)
    output_dir_path = Path(final_output_path).parent

    # Generate transcript if needed
    processor: Optional[VideoProcessor] = None
    if transcript_file is None and media_file:
        output_dir_path.mkdir(parents=True, exist_ok=True)
        processor = VideoProcessor(str(media_file.parent), output_dir=str(output_dir_path))
        transcript_output = str(output_dir_path / "transcript.vtt")

        step_start("Generating transcript", {"Input": str(media_file)})
        with status_spinner("Transcribing"):
            transcript_result = processor.generate_transcript(str(media_file), output_path=transcript_output)
        step_complete("Transcript generated", transcript_result)

        transcript_file = Path(transcript_result)
        transcript_generated = True

    # Handle timestamps path
    timestamps_str = None
    if timestamps:
        timestamps_str = normalize_path(str(timestamps))
        if not Path(timestamps_str).exists():
            step_warning(f"Timestamps file not found: {timestamps_str}")
            timestamps_str = None

    # Find media file if not already set (for video_path param in generate_description)
    if media_file is None:
        search_dirs = [transcript_file.parent, transcript_file.parent.parent]
        video_candidates = []
        for candidate_dir in search_dirs:
            if candidate_dir.exists():
                video_candidates.extend(_find_supported_videos(candidate_dir))

        if video_candidates:
            media_file = video_candidates[0]
        else:
            # Use transcript file's stem as fallback title
            media_file = transcript_file

    # Create processor if needed
    if processor is None:
        processor = VideoProcessor(str(transcript_file.parent), output_dir=str(output_dir_path))

    # Build links list
    links_list = []

    # Video-specific links first
    if code_link:
        links_list.append({"description": "📦 Code from this video", "url": code_link})
    if article_link:
        links_list.append({"description": "📝 Written version", "url": article_link})

    # Persistent links from config
    if links:
        config_links = get_links()
        if not config_links:
            config_links = prompt_links_setup()
        links_list.extend(config_links)

    step_start("Generating description", {"Transcript": str(transcript_file), "Output": final_output_path})

    with status_spinner("Processing"):
        description_result = processor.generate_description(
            video_path=str(media_file),
            transcript_path=str(transcript_file),
            output_path=final_output_path,
            timestamps_path=timestamps_str,
            links=links_list if links_list else None,
        )

    step_complete("Description generated", description_result)

    # Update metadata
    _update_description_metadata(output_dir_path, transcript_file if transcript_generated else None, description_result)


def _update_description_metadata(output_dir: Path, transcript_file: Optional[Path], description_path: str) -> None:
    """Update metadata.json with description content."""
    metadata_path = output_dir / "metadata.json"
    existing = _read_metadata(metadata_path) or {}

    if transcript_file:
        try:
            existing["transcript"] = transcript_file.read_text(encoding="utf-8")
            existing["transcript_format"] = transcript_file.suffix.lstrip(".").lower()
        except OSError:
            pass

    try:
        existing["description"] = Path(description_path).read_text(encoding="utf-8")
    except OSError:
        pass

    _write_metadata(metadata_path, existing)


@content_app.command("seo")
def seo(
    transcript_path: Optional[Path] = typer.Option(None, "--transcript-path", "-t", help="Path to transcript (.vtt)"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o", help="Output directory"),
) -> None:
    """Generate SEO keywords from transcript."""
    if not validate_ai_env_vars():
        raise typer.Exit(1)

    if transcript_path is None:
        transcript_path_str = ask_path("Path to transcript (.vtt)", required=True)
        transcript_path = Path(transcript_path_str)
    else:
        transcript_path = Path(normalize_path(str(transcript_path)))

    if not transcript_path.exists() or not transcript_path.is_file():
        step_error(f"Invalid transcript file: {transcript_path}")
        raise typer.Exit(1)

    transcript_dir = transcript_path.parent
    output_dir_path = Path(normalize_path(str(output_dir))) if output_dir else transcript_dir

    step_start("Generating SEO keywords", {"Transcript": str(transcript_path)})

    # Check if description exists, generate if needed
    description_path = output_dir_path / "description.md"
    processor = VideoProcessor(str(transcript_dir), output_dir=str(output_dir_path))

    if not description_path.exists():
        step_warning("Description not found. Generating description first...")
        search_dirs = [transcript_dir, transcript_dir.parent]
        video_candidates = []
        for candidate_dir in search_dirs:
            if candidate_dir.exists():
                video_candidates.extend(_find_supported_videos(candidate_dir))

        if not video_candidates:
            step_error("No video file found near transcript")
            raise typer.Exit(1)

        video_path = str(video_candidates[0])
        processor = VideoProcessor(str(Path(video_path).parent), output_dir=str(output_dir_path))

        with status_spinner("Generating description"):
            description_path = processor.generate_description(
                video_path=video_path,
                transcript_path=str(transcript_path),
                output_path=str(output_dir_path / "description.md"),
            )

    with status_spinner("Processing"):
        keywords_path = processor.generate_seo_keywords(str(description_path))

    step_complete("SEO keywords generated", keywords_path)

    # Update metadata
    _update_seo_metadata(output_dir_path, keywords_path)


def _update_seo_metadata(output_dir: Path, keywords_path: str) -> None:
    """Update metadata.json with SEO keywords."""
    metadata_path = output_dir / "metadata.json"
    existing = _read_metadata(metadata_path) or {}

    try:
        existing["seo_keywords"] = Path(keywords_path).read_text(encoding="utf-8")
    except OSError:
        pass

    _write_metadata(metadata_path, existing)


@content_app.command("linkedin")
def linkedin(
    transcript_path: Optional[Path] = typer.Option(None, "--transcript-path", "-t", help="Path to transcript (.vtt)"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o", help="Output directory"),
    output_path: Optional[Path] = typer.Option(None, "--output-path", help="Full path for output file"),
) -> None:
    """Generate LinkedIn post from transcript."""
    if not validate_ai_env_vars():
        raise typer.Exit(1)

    if transcript_path is None:
        transcript_path_str = ask_path("Path to transcript (.vtt)", required=True)
        transcript_path = Path(transcript_path_str)
    else:
        transcript_path = Path(normalize_path(str(transcript_path)))

    if not transcript_path.exists() or not transcript_path.is_file():
        step_error(f"Invalid transcript file: {transcript_path}")
        raise typer.Exit(1)

    transcript_dir = transcript_path.parent
    output_dir_path = Path(normalize_path(str(output_dir))) if output_dir else transcript_dir
    final_output_path = str(Path(normalize_path(str(output_path)))) if output_path else str(output_dir_path / "linkedin_post.md")

    step_start("Generating LinkedIn post", {"Transcript": str(transcript_path), "Output": final_output_path})

    with status_spinner("Processing"):
        processor = VideoProcessor(str(transcript_dir), output_dir=str(output_dir_path))
        linkedin_path = processor.generate_linkedin_post(str(transcript_path), output_path=final_output_path)

    step_complete("LinkedIn post generated", linkedin_path)

    # Update metadata
    _update_social_metadata(output_dir_path, "linkedin_post", linkedin_path)


@content_app.command("twitter")
def twitter(
    transcript_path: Optional[Path] = typer.Option(None, "--transcript-path", "-t", help="Path to transcript (.vtt)"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o", help="Output directory"),
    output_path: Optional[Path] = typer.Option(None, "--output-path", help="Full path for output file"),
) -> None:
    """Generate Twitter post from transcript."""
    if not validate_ai_env_vars():
        raise typer.Exit(1)

    if transcript_path is None:
        transcript_path_str = ask_path("Path to transcript (.vtt)", required=True)
        transcript_path = Path(transcript_path_str)
    else:
        transcript_path = Path(normalize_path(str(transcript_path)))

    if not transcript_path.exists() or not transcript_path.is_file():
        step_error(f"Invalid transcript file: {transcript_path}")
        raise typer.Exit(1)

    transcript_dir = transcript_path.parent
    output_dir_path = Path(normalize_path(str(output_dir))) if output_dir else transcript_dir
    final_output_path = str(Path(normalize_path(str(output_path)))) if output_path else str(output_dir_path / "twitter_post.md")

    step_start("Generating Twitter post", {"Transcript": str(transcript_path), "Output": final_output_path})

    with status_spinner("Processing"):
        processor = VideoProcessor(str(transcript_dir), output_dir=str(output_dir_path))
        twitter_path = processor.generate_twitter_post(str(transcript_path), output_path=final_output_path)

    step_complete("Twitter post generated", twitter_path)

    # Update metadata
    _update_social_metadata(output_dir_path, "twitter_post", twitter_path)


def _update_social_metadata(output_dir: Path, key: str, content_path: str) -> None:
    """Update metadata.json with social post content."""
    metadata_path = output_dir / "metadata.json"
    existing = _read_metadata(metadata_path) or {}

    try:
        existing[key] = Path(content_path).read_text(encoding="utf-8")
    except OSError:
        pass

    _write_metadata(metadata_path, existing)


@content_app.command("context-cards")
def context_cards(
    input_transcript: Optional[Path] = typer.Option(None, "--input-transcript", "-t", help="Path to transcript (.vtt)"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o", help="Output directory"),
    output_path: Optional[Path] = typer.Option(None, "--output-path", help="Full path for output file"),
) -> None:
    """Generate context cards from transcript."""
    if not validate_ai_env_vars():
        raise typer.Exit(1)

    if input_transcript is None:
        transcript_path_str = ask_path("Path to transcript (.vtt)", required=True)
        input_transcript = Path(transcript_path_str)
    else:
        input_transcript = Path(normalize_path(str(input_transcript)))

    if not input_transcript.exists() or not input_transcript.is_file():
        step_error(f"Invalid transcript file: {input_transcript}")
        raise typer.Exit(1)

    transcript_dir = input_transcript.parent
    output_dir_path = Path(normalize_path(str(output_dir))) if output_dir else transcript_dir
    final_output_path = str(Path(normalize_path(str(output_path)))) if output_path else str(output_dir_path / "context-cards.md")

    step_start("Generating context cards", {"Transcript": str(input_transcript), "Output": final_output_path})

    with status_spinner("Processing"):
        processor = VideoProcessor(str(transcript_dir), output_dir=str(output_dir_path))
        cards_path = processor.generate_context_cards(str(input_transcript), output_path=final_output_path)

    if cards_path:
        step_complete("Context cards generated", cards_path)
        _update_context_cards_metadata(output_dir_path, cards_path)
    else:
        step_error("Failed to generate context cards")
        raise typer.Exit(1)


def _update_context_cards_metadata(output_dir: Path, cards_path: str) -> None:
    """Update metadata.json with context cards."""
    metadata_path = output_dir / "metadata.json"
    existing = _read_metadata(metadata_path) or {}

    try:
        existing["context_cards"] = Path(cards_path).read_text(encoding="utf-8")
    except OSError:
        pass

    _write_metadata(metadata_path, existing)


@content_app.command("summary")
def summary(
    transcript_path: Optional[Path] = typer.Option(None, "--transcript-path", "-t", help="Path to transcript (.vtt)"),
    output_dir: Optional[Path] = typer.Option(None, "--output-dir", "-o", help="Output directory"),
    output_path: Optional[Path] = typer.Option(None, "--output-path", help="Full path for output file"),
    length: Optional[str] = typer.Option(None, "--length", "-l", help="Summary length (short/medium/long)"),
    difficulty: Optional[str] = typer.Option(None, "--difficulty", "-d", help="Difficulty (beginner/intermediate/advanced)"),
    no_keywords: bool = typer.Option(False, "--no-keywords", help="Disable SEO keyword generation"),
    target_audience: Optional[str] = typer.Option(None, "--target-audience", help="Target audience override"),
    output_format: str = typer.Option("markdown", "--output-format", "-f", help="Output format (markdown/json)"),
    disable: bool = typer.Option(False, "--disable", help="Skip summary generation"),
) -> None:
    """Generate a structured technical summary from a transcript."""
    if not validate_ai_env_vars():
        raise typer.Exit(1)

    if disable:
        console.print("[dim]Summary generation disabled.[/dim]")
        return

    if transcript_path is None:
        transcript_path_str = ask_path("Path to transcript (.vtt)", required=True)
        transcript_path = Path(transcript_path_str)
    else:
        transcript_path = Path(normalize_path(str(transcript_path)))

    if not transcript_path.exists() or not transcript_path.is_file():
        step_error(f"Invalid transcript file: {transcript_path}")
        raise typer.Exit(1)

    transcript_dir = transcript_path.parent
    default_output_dir = transcript_dir / "summaries"
    output_dir_path = Path(normalize_path(str(output_dir))) if output_dir else default_output_dir

    extension = "json" if output_format.lower() == "json" else "md"
    if output_path:
        final_output_path = str(Path(normalize_path(str(output_path))))
    else:
        final_output_path = str(output_dir_path / f"{transcript_path.stem}_summary.{extension}")

    summary_config = {
        "enabled": True,
        "length": length or "medium",
        "difficulty": difficulty or "intermediate",
        "include_keywords": not no_keywords,
        "output_format": output_format.lower(),
    }
    if target_audience:
        summary_config["target_audience"] = target_audience

    step_start("Generating summary", {"Transcript": str(transcript_path), "Output": final_output_path})

    with status_spinner("Processing"):
        processor = VideoProcessor(str(transcript_dir), output_dir=str(transcript_dir))
        summary_path = processor.generate_summary(
            transcript_path=str(transcript_path),
            output_path=final_output_path,
            config=summary_config,
        )

    if summary_path:
        step_complete("Summary generated", summary_path)
    else:
        step_error("Failed to generate summary")
        raise typer.Exit(1)


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
