"""AI-powered content generation commands: transcript, description, context-cards."""

from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

import typer

from video_tool import VideoProcessor
from video_tool.cli import generate_app, ensure_openai_key, ensure_groq_key
from video_tool.config import get_llm_config, ensure_config, get_links, prompt_links_setup
from video_tool.ui import (
    ask_path,
    console,
    normalize_path,
    status_spinner,
    step_complete,
    step_error,
    step_start,
    step_warning,
)
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


@generate_app.command("transcript")
def transcript(
    input_path: Optional[Path] = typer.Option(None, "--input", "-i", help="Input video or audio file"),
    output_path: Optional[Path] = typer.Option(None, "--output-path", "-o", help="Output VTT file path"),
) -> None:
    """Generate VTT transcript from video or audio using Groq Whisper."""
    if not ensure_groq_key():
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


@generate_app.command("description")
def description(
    input_path: Optional[Path] = typer.Option(None, "--input", "-i", help="Input file (video/audio/vtt/md/txt)"),
    output_path: Optional[Path] = typer.Option(None, "--output-path", "-o", help="Full path for output description"),
    timestamps: Optional[Path] = typer.Option(None, "--timestamps", "-t", help="Path to timestamps JSON"),
    links: bool = typer.Option(False, "--links", "-l", help="Include persistent links from config"),
    code_link: Optional[str] = typer.Option(None, "--code-link", help="Link to code repository"),
    article_link: Optional[str] = typer.Option(None, "--article-link", help="Link to written article"),
) -> None:
    """Generate video description from transcript or media file."""
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

    # Validate keys based on input type
    # Always need OpenAI for LLM description generation
    if not ensure_openai_key():
        raise typer.Exit(1)
    # Need Groq if we have media file (will generate transcript)
    if media_file and not ensure_groq_key():
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

    llm_config = get_llm_config("description")
    step_start("Generating description", {
        "Transcript": str(transcript_file),
        "Output": final_output_path,
        "Model": llm_config.model,
        "Provider": llm_config.base_url,
    })

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


@generate_app.command("context-cards")
def context_cards(
    input_path: Optional[Path] = typer.Option(None, "--input", "-i", help="Input file (video/audio/vtt)"),
    output_path: Optional[Path] = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    """Generate context cards from transcript or media file."""
    transcript_file: Optional[Path] = None
    media_file: Optional[Path] = None
    transcript_generated = False

    # Resolve input
    if input_path is None:
        input_str = ask_path(f"Input file ({SUPPORTED_MEDIA_LABEL}, VTT)", required=True)
        input_path = Path(input_str)
    else:
        input_path = Path(normalize_path(str(input_path)))

    if not input_path.exists() or not input_path.is_file():
        step_error(f"Invalid input file: {input_path}")
        raise typer.Exit(1)

    # Determine input type
    suffix = input_path.suffix.lower()
    if suffix == ".vtt":
        transcript_file = input_path
    elif suffix in SUPPORTED_VIDEO_SUFFIXES + SUPPORTED_AUDIO_SUFFIXES:
        media_file = input_path
    else:
        step_error(f"Unsupported file type: {suffix}. Use VTT transcript or video/audio.")
        raise typer.Exit(1)

    # Validate keys based on input type
    # Always need OpenAI for LLM context card generation
    if not ensure_openai_key():
        raise typer.Exit(1)
    # Need Groq if we have media file (will generate transcript)
    if media_file and not ensure_groq_key():
        raise typer.Exit(1)

    # Determine default output path
    default_output_path = input_path.parent / "context-cards.md"

    # Resolve output path
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

    # Create processor if needed
    if processor is None:
        processor = VideoProcessor(str(transcript_file.parent), output_dir=str(output_dir_path))

    llm_config = get_llm_config("context_cards")
    step_start("Generating context cards", {
        "Transcript": str(transcript_file),
        "Output": final_output_path,
        "Model": llm_config.model,
        "Provider": llm_config.base_url,
    })

    with status_spinner("Processing"):
        cards_path = processor.generate_context_cards(str(transcript_file), output_path=final_output_path)

    if cards_path:
        step_complete("Context cards generated", cards_path)
        _update_context_cards_metadata(output_dir_path, cards_path, transcript_file if transcript_generated else None)
    else:
        step_error("Failed to generate context cards")
        raise typer.Exit(1)


def _update_context_cards_metadata(output_dir: Path, cards_path: str, transcript_file: Optional[Path] = None) -> None:
    """Update metadata.json with context cards and optional transcript."""
    metadata_path = output_dir / "metadata.json"
    existing = _read_metadata(metadata_path) or {}

    if transcript_file:
        try:
            existing["transcript"] = transcript_file.read_text(encoding="utf-8")
            existing["transcript_format"] = transcript_file.suffix.lstrip(".").lower()
        except OSError:
            pass

    try:
        existing["context_cards"] = Path(cards_path).read_text(encoding="utf-8")
    except OSError:
        pass

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
