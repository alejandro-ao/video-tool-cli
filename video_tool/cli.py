"""
Command-line interface for video-tool.

Each tool can be called independently with its own arguments.
If arguments are not provided, the user will be prompted interactively.
"""

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, cast

from dotenv import load_dotenv
from rich.console import Console
from rich.prompt import Prompt

from video_tool import VideoProcessor

console = Console()


def normalize_path(raw: str) -> str:
    """Normalize shell-style input paths (quotes / escaped spaces)."""
    trimmed = raw.strip()
    # Remove surrounding quotes if present
    if trimmed.startswith('"') and trimmed.endswith('"'):
        trimmed = trimmed[1:-1]
    elif trimmed.startswith("'") and trimmed.endswith("'"):
        trimmed = trimmed[1:-1]
    # Handle escaped spaces (shell passes these literally)
    trimmed = trimmed.replace("\\ ", " ")
    # Expand user home directory and resolve to absolute path
    return str(Path(trimmed).expanduser().resolve())


def ask_required_path(prompt_text: str) -> str:
    """Prompt until a non-empty path-like value is provided."""
    while True:
        response = Prompt.ask(
            f"[bold cyan]{prompt_text}[/]",
            console=console,
        )
        normalized = normalize_path(response)
        if normalized:
            return normalized
        console.print("[yellow]Please provide a value.[/]")


def ask_required_text(prompt_text: str) -> str:
    """Prompt until a non-empty text value is provided."""
    while True:
        response = Prompt.ask(
            f"[bold cyan]{prompt_text}[/]",
            console=console,
        ).strip()
        if response:
            return response
        console.print("[yellow]Please provide a value.[/]")


def ask_optional_text(prompt_text: str, default: Optional[str] = None) -> Optional[str]:
    """Prompt for optional text input."""
    if default:
        response = Prompt.ask(
            f"[bold cyan]{prompt_text}[/]",
            default=default,
            console=console,
        ).strip()
    else:
        response = Prompt.ask(
            f"[bold cyan]{prompt_text}[/] ([dim]optional[/])",
            default="",
            show_default=False,
            console=console,
        ).strip()
    return response or default


def ask_yes_no(prompt_text: str, default: bool = False) -> bool:
    """Prompt the user for a yes/no response."""
    default_str = "y" if default else "n"
    while True:
        response = (
            Prompt.ask(
                f"[bold cyan]{prompt_text}[/] (y/n)",
                default=default_str,
                show_default=True,
                console=console,
            )
            .strip()
            .lower()
        )
        if response in ("y", "yes"):
            return True
        if response in ("n", "no"):
            return False
        console.print("[yellow]Please enter 'y' or 'n'.[/]")


def cmd_silence_removal(args: argparse.Namespace) -> None:
    """Run silence removal on videos."""
    input_dir = args.input_dir
    if not input_dir:
        input_dir = ask_required_path("Input directory (containing videos)")
    else:
        input_dir = normalize_path(input_dir)

    input_path = Path(input_dir).expanduser().resolve()
    if not input_path.exists() or not input_path.is_dir():
        console.print(f"[bold red]Error:[/] Invalid input directory: {input_dir}")
        sys.exit(1)

    # Handle output directory
    output_dir = None
    if args.output_dir:
        output_dir = normalize_path(args.output_dir)

    console.print(f"[cyan]Running silence removal...[/]")
    console.print(f"  Input: {input_path}")
    console.print(f"  Output: {output_dir or str(input_path / 'output')}\n")

    processor = VideoProcessor(str(input_path), output_dir=output_dir)
    processed_dir = processor.remove_silences()

    console.print(f"[green]✓ Silence removal complete![/]")
    console.print(f"  Processed videos: {processed_dir}")


def cmd_concat(args: argparse.Namespace) -> None:
    """Concatenate videos."""
    input_dir = args.input_dir
    if not input_dir:
        input_dir = ask_required_path("Input directory (containing videos to concatenate)")
    else:
        input_dir = normalize_path(input_dir)

    input_path = Path(input_dir).expanduser().resolve()
    if not input_path.exists() or not input_path.is_dir():
        console.print(f"[bold red]Error:[/] Invalid input directory: {input_dir}")
        sys.exit(1)

    # Handle output path for the concatenated video file
    output_path = None
    if args.output_path:
        output_path = normalize_path(args.output_path)
    else:
        # Default: input_dir/output/concatenated.mp4
        output_path = str(input_path / "output" / "concatenated.mp4")

    skip_reprocessing = args.fast_concat if args.fast_concat is not None else False

    console.print(f"[cyan]Running video concatenation...[/]")
    console.print(f"  Input: {input_path}")
    console.print(f"  Output file: {output_path}")
    console.print(f"  Fast mode: {'Yes' if skip_reprocessing else 'No'}\n")

    processor = VideoProcessor(str(input_path))
    output_video = processor.concatenate_videos(
        skip_reprocessing=skip_reprocessing,
        output_path=output_path
    )

    console.print(f"[green]✓ Concatenation complete![/]")
    console.print(f"  Output video: {output_video}")


def cmd_timestamps(args: argparse.Namespace) -> None:
    """Generate timestamps for videos."""
    input_dir = args.input_dir
    if not input_dir:
        input_dir = ask_required_path("Input directory (containing videos) or path to a video file")
    else:
        input_dir = normalize_path(input_dir)

    input_path = Path(input_dir).expanduser().resolve()
    if not input_path.exists():
        console.print(f"[bold red]Error:[/] Invalid input path: {input_dir}")
        sys.exit(1)

    is_video_input = input_path.is_file()
    if is_video_input and input_path.suffix.lower() != ".mp4":
        console.print(f"[bold red]Error:[/] Input file must be an MP4 video: {input_dir}")
        sys.exit(1)

    base_dir = input_path.parent if is_video_input else input_path

    # Handle output path for the JSON file
    output_path = None
    if args.output_path:
        output_path = normalize_path(args.output_path)
    else:
        # Default: base_dir/output/timestamps.json
        output_path = str(base_dir / "output" / "timestamps.json")

    transcript_path = None
    use_transcript = False
    granularity = args.granularity
    timestamp_notes = args.timestamp_notes

    if is_video_input:
        use_transcript = True
        transcript_input = args.stamps_from_transcript
        if transcript_input is None:
            transcript_input = ask_optional_text(
                "Path to transcript for this video (leave blank to auto-generate)",
                default="",
            )
        if transcript_input:
            transcript_path = normalize_path(transcript_input)
            transcript_file = Path(transcript_path)
            if not transcript_file.exists():
                console.print(
                    f"[yellow]Transcript not found at {transcript_path}. A new transcript will be generated automatically.[/]"
                )
                transcript_path = None
        else:
            console.print(
                "[yellow]No transcript path provided. A transcript will be generated automatically for timestamps.[/]"
            )
    else:
        if args.stamps_from_transcript is None:
            per_clip = ask_yes_no("Do you want one chapter per clip?", default=True)
            use_transcript = not per_clip
        else:
            use_transcript = True

        if use_transcript:
            transcript_input = args.stamps_from_transcript
            if transcript_input == "":
                transcript_input = ask_optional_text(
                    "Path to transcript for timestamps (leave blank to auto-generate)",
                    default="",
                )
            if transcript_input:
                transcript_path = normalize_path(transcript_input)
                transcript_file = Path(transcript_path)
                if not transcript_file.exists():
                    console.print(
                        f"[yellow]Transcript not found at {transcript_path}. A new transcript will be generated automatically.[/]"
                    )
                    transcript_path = None
            else:
                console.print(
                    "[yellow]No transcript path provided. A transcript will be generated automatically for timestamps.[/]"
                )

    if not granularity:
        granularity = ask_optional_text(
            "Granularity for timestamps (low/medium/high)", default="medium"
        )
    if granularity:
        granularity = granularity.lower().strip()
        if granularity not in {"low", "medium", "high"}:
            console.print("[yellow]Invalid granularity; defaulting to 'medium'.[/]")
            granularity = "medium"
    else:
        granularity = "medium"

    if timestamp_notes is None:
        timestamp_notes = ask_optional_text(
            "Additional instructions for timestamps (optional)", default=""
        )

    console.print(f"[cyan]Generating timestamps...[/]")
    console.print(f"  Input: {input_path}")
    console.print(f"  Output file: {output_path}\n")

    processor = VideoProcessor(str(base_dir))
    timestamps_info = processor.generate_timestamps(
        output_path=output_path,
        transcript_path=transcript_path,
        stamps_from_transcript=use_transcript,
        granularity=granularity,
        timestamp_notes=timestamp_notes,
        video_path=str(input_path) if is_video_input else None,
    )

    console.print(f"[green]✓ Timestamps generated![/]")
    metadata = timestamps_info.get("metadata", {}) if isinstance(timestamps_info, dict) else {}
    transcript_used = metadata.get("transcript_path")
    if use_transcript:
        if transcript_used:
            console.print(f"  Transcript used: {transcript_used}")
            if metadata.get("transcript_generated"):
                console.print("  Transcript was generated automatically.")
        else:
            console.print("  Transcript: fallback to clip-based chapter timing.")
    console.print(f"  Timestamps file: {output_path}")


def cmd_transcript(args: argparse.Namespace) -> None:
    """Generate transcript for a video."""
    video_path = args.video_path
    if not video_path:
        video_path = ask_required_path("Path to video file")
    else:
        video_path = normalize_path(video_path)

    video_file = Path(video_path).expanduser().resolve()
    if not video_file.exists() or not video_file.is_file():
        console.print(f"[bold red]Error:[/] Invalid video file: {video_path}")
        sys.exit(1)

    # Handle output path for the transcript file
    output_path = None
    if args.output_path:
        output_path = normalize_path(args.output_path)

    console.print(f"[cyan]Generating transcript...[/]")
    console.print(f"  Video: {video_file}")
    if output_path:
        console.print(f"  Output file: {output_path}\n")
    else:
        console.print(f"  Output file: {video_file.parent}/output/transcript.vtt\n")

    # Use the video's parent directory as input_dir
    processor = VideoProcessor(str(video_file.parent))
    transcript_path = processor.generate_transcript(str(video_file), output_path=output_path)

    console.print(f"[green]✓ Transcript generated![/]")
    console.print(f"  Transcript: {transcript_path}")


def cmd_context_cards(args: argparse.Namespace) -> None:
    """Generate context cards from a transcript file."""
    transcript_path = args.input_transcript
    if not transcript_path:
        transcript_path = ask_required_path("Path to transcript file (.vtt)")
    else:
        transcript_path = normalize_path(transcript_path)

    transcript_file = Path(transcript_path).expanduser().resolve()
    if not transcript_file.exists() or not transcript_file.is_file():
        console.print(f"[bold red]Error:[/] Invalid transcript file: {transcript_path}")
        sys.exit(1)

    output_path = None
    if args.output_path:
        output_path = normalize_path(args.output_path)
        output_file = Path(output_path).expanduser()
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_path = str(output_file)

    console.print(f"[cyan]Generating context cards...[/]")
    console.print(f"  Transcript: {transcript_file}")
    if output_path:
        console.print(f"  Output file: {output_path}\n")
    else:
        console.print("\n")

    transcript_dir = transcript_file.parent
    processor = VideoProcessor(str(transcript_dir), output_dir=str(transcript_dir))

    cards_path = processor.generate_context_cards(
        str(transcript_file),
        output_path=output_path,
    )

    if cards_path:
        console.print(f"[green]✓ Context cards generated![/]")
        console.print(f"  Context cards: {cards_path}")
    else:
        console.print(f"[bold red]Error:[/] Failed to generate context cards")
        sys.exit(1)


def cmd_description(args: argparse.Namespace) -> None:
    """Generate video description from transcript."""
    transcript_path = args.transcript_path
    if not transcript_path:
        transcript_path = ask_required_path("Path to video transcript (.vtt file)")
    else:
        transcript_path = normalize_path(transcript_path)

    transcript_file = Path(transcript_path).expanduser().resolve()
    if not transcript_file.exists() or not transcript_file.is_file():
        console.print(f"[bold red]Error:[/] Invalid transcript file: {transcript_path}")
        sys.exit(1)

    transcript_dir = transcript_file.parent

    repo_url = args.repo_url
    if not repo_url:
        repo_url = ask_optional_text("Repository URL", None)

    # Handle output path for the description file
    if args.output_path:
        output_path = normalize_path(args.output_path)
    else:
        output_path = str(transcript_dir / "description.md")

    # Handle timestamps path
    timestamps_path = None
    if args.timestamps_path:
        timestamps_path = normalize_path(args.timestamps_path)
        timestamps_file = Path(timestamps_path)
        if not timestamps_file.exists():
            console.print(f"[bold yellow]Warning:[/] Timestamps file not found: {timestamps_path}")
            console.print("[yellow]Continuing without timestamps...[/]")
            timestamps_path = None

    console.print(f"[cyan]Generating description...[/]")
    console.print(f"  Transcript: {transcript_file}")
    console.print(f"  Repository: {repo_url or 'None'}")
    if timestamps_path:
        console.print(f"  Timestamps: {timestamps_path}")
    console.print(f"  Output file: {output_path}\n")

    search_dirs = [transcript_dir]
    parent_dir = transcript_dir.parent
    if parent_dir != transcript_dir:
        search_dirs.append(parent_dir)

    # Find the video file (assume it's in the transcript directory or its parent)
    video_candidates = []
    for candidate_dir in search_dirs:
        video_candidates.extend(sorted(candidate_dir.glob("*.mp4")))

    if not video_candidates:
        console.print(f"[bold red]Error:[/] No video file found near transcript")
        sys.exit(1)

    video_path = str(video_candidates[0])
    video_dir = Path(video_path).parent

    processor = VideoProcessor(str(video_dir), output_dir=str(transcript_dir))

    description_path = processor.generate_description(
        video_path=video_path,
        repo_url=repo_url,
        transcript_path=str(transcript_file),
        output_path=output_path,
        timestamps_path=timestamps_path
    )

    console.print(f"[green]✓ Description generated![/]")
    console.print(f"  Description: {description_path}")


def cmd_seo(args: argparse.Namespace) -> None:
    """Generate SEO keywords from transcript."""
    transcript_path = args.transcript_path
    if not transcript_path:
        transcript_path = ask_required_path("Path to video transcript (.vtt file)")
    else:
        transcript_path = normalize_path(transcript_path)

    transcript_file = Path(transcript_path).expanduser().resolve()
    if not transcript_file.exists() or not transcript_file.is_file():
        console.print(f"[bold red]Error:[/] Invalid transcript file: {transcript_path}")
        sys.exit(1)

    transcript_dir = transcript_file.parent
    search_dirs = [transcript_dir]
    parent_dir = transcript_dir.parent
    if parent_dir != transcript_dir:
        search_dirs.append(parent_dir)

    console.print(f"[cyan]Generating SEO keywords...[/]")
    console.print(f"  Transcript: {transcript_file}\n")

    processor: VideoProcessor = VideoProcessor(str(transcript_dir), output_dir=str(transcript_dir))

    # First generate description if it doesn't exist
    description_path = transcript_dir / "description.md"
    if not description_path.exists():
        console.print(f"[yellow]Description not found. Generating description first...[/]")

        # Find video file
        video_candidates = []
        for candidate_dir in search_dirs:
            video_candidates.extend(sorted(candidate_dir.glob("*.mp4")))

        if not video_candidates:
            console.print(f"[bold red]Error:[/] No video file found near transcript")
            sys.exit(1)

        video_path = str(video_candidates[0])
        video_dir = Path(video_path).parent

        processor = VideoProcessor(str(video_dir), output_dir=str(transcript_dir))
        description_path = processor.generate_description(
            video_path=video_path,
            transcript_path=str(transcript_file),
            output_path=str(description_path),
        )

    keywords_path = processor.generate_seo_keywords(str(description_path))

    console.print(f"[green]✓ SEO keywords generated![/]")
    console.print(f"  Keywords: {keywords_path}")


def cmd_linkedin(args: argparse.Namespace) -> None:
    """Generate LinkedIn post from transcript."""
    transcript_path = args.transcript_path
    if not transcript_path:
        transcript_path = ask_required_path("Path to video transcript (.vtt file)")
    else:
        transcript_path = normalize_path(transcript_path)

    transcript_file = Path(transcript_path).expanduser().resolve()
    if not transcript_file.exists() or not transcript_file.is_file():
        console.print(f"[bold red]Error:[/] Invalid transcript file: {transcript_path}")
        sys.exit(1)

    # Handle output path for the LinkedIn post file
    transcript_dir = transcript_file.parent
    if args.output_path:
        output_path = normalize_path(args.output_path)
    else:
        output_path = str(transcript_dir / "linkedin_post.md")

    console.print(f"[cyan]Generating LinkedIn post...[/]")
    console.print(f"  Transcript: {transcript_file}")
    console.print(f"  Output file: {output_path}\n")

    processor = VideoProcessor(str(transcript_dir), output_dir=str(transcript_dir))
    linkedin_path = processor.generate_linkedin_post(str(transcript_file), output_path=output_path)

    console.print(f"[green]✓ LinkedIn post generated![/]")
    console.print(f"  LinkedIn post: {linkedin_path}")


def cmd_twitter(args: argparse.Namespace) -> None:
    """Generate Twitter post from transcript."""
    transcript_path = args.transcript_path
    if not transcript_path:
        transcript_path = ask_required_path("Path to video transcript (.vtt file)")
    else:
        transcript_path = normalize_path(transcript_path)

    transcript_file = Path(transcript_path).expanduser().resolve()
    if not transcript_file.exists() or not transcript_file.is_file():
        console.print(f"[bold red]Error:[/] Invalid transcript file: {transcript_path}")
        sys.exit(1)

    # Handle output path for the Twitter post file
    transcript_dir = transcript_file.parent
    if args.output_path:
        output_path = normalize_path(args.output_path)
    else:
        output_path = str(transcript_dir / "twitter_post.md")

    console.print(f"[cyan]Generating Twitter post...[/]")
    console.print(f"  Transcript: {transcript_file}")
    console.print(f"  Output file: {output_path}\n")

    processor = VideoProcessor(str(transcript_dir), output_dir=str(transcript_dir))
    twitter_path = processor.generate_twitter_post(str(transcript_file), output_path=output_path)

    console.print(f"[green]✓ Twitter post generated![/]")
    console.print(f"  Twitter post: {twitter_path}")


def cmd_bunny_video(args: argparse.Namespace) -> None:
    """Upload video to Bunny.net."""
    video_path = args.video_path
    if not video_path:
        video_path = ask_required_path("Path to video file to upload")
    else:
        video_path = normalize_path(video_path)

    video_file = Path(video_path).expanduser().resolve()
    if not video_file.exists() or not video_file.is_file():
        console.print(f"[bold red]Error:[/] Invalid video file: {video_path}")
        sys.exit(1)

    # Get required Bunny credentials
    library_id = args.bunny_library_id or os.getenv("BUNNY_LIBRARY_ID")
    if not library_id:
        library_id = ask_optional_text("Bunny Library ID", None)

    access_key = args.bunny_access_key or os.getenv("BUNNY_ACCESS_KEY")
    if not access_key:
        access_key = ask_optional_text("Bunny Access Key", None)

    if not library_id or not access_key:
        console.print(f"[bold red]Error:[/] BUNNY_LIBRARY_ID and BUNNY_ACCESS_KEY are required")
        sys.exit(1)

    collection_id = args.bunny_collection_id or os.getenv("BUNNY_COLLECTION_ID")

    console.print(f"[cyan]Uploading video to Bunny.net...[/]")
    console.print(f"  Video: {video_file}")
    console.print(f"  Library ID: {library_id}\n")

    processor = VideoProcessor(str(video_file.parent))
    result = processor.upload_bunny_video(
        video_path=str(video_file),
        library_id=library_id,
        access_key=access_key,
        collection_id=collection_id,
    )

    if result:
        console.print(f"[green]✓ Video uploaded to Bunny.net![/]")
        console.print(f"  Video ID: {result.get('video_id')}")
    else:
        console.print(f"[bold red]Error:[/] Failed to upload video to Bunny.net")
        sys.exit(1)


def cmd_bunny_transcript(args: argparse.Namespace) -> None:
    """Upload transcript captions to an existing Bunny.net video."""
    video_id = args.video_id or os.getenv("BUNNY_VIDEO_ID")
    if not video_id:
        video_id = ask_required_text("Bunny Video ID")

    library_id = args.bunny_library_id or os.getenv("BUNNY_LIBRARY_ID")
    if not library_id:
        library_id = ask_optional_text("Bunny Library ID", None)

    access_key = args.bunny_access_key or os.getenv("BUNNY_ACCESS_KEY")
    if not access_key:
        access_key = ask_optional_text("Bunny Access Key", None)

    if not library_id or not access_key:
        console.print(f"[bold red]Error:[/] BUNNY_LIBRARY_ID and BUNNY_ACCESS_KEY are required")
        sys.exit(1)

    transcript_path = args.transcript_path
    if transcript_path:
        transcript_path = normalize_path(transcript_path)
    else:
        transcript_path = ask_required_path("Path to transcript file (.vtt)")

    transcript_file = Path(transcript_path).expanduser().resolve()
    if not transcript_file.exists() or not transcript_file.is_file():
        console.print(f"[bold red]Error:[/] Invalid transcript file: {transcript_path}")
        sys.exit(1)

    language = args.language or os.getenv("BUNNY_CAPTION_LANGUAGE") or "en"
    language = language.strip() or "en"

    console.print(f"[cyan]Uploading transcript to Bunny.net...[/]")
    console.print(f"  Transcript: {transcript_file}")
    console.print(f"  Video ID: {video_id}")
    console.print(f"  Language: {language}\n")

    processor = VideoProcessor(str(transcript_file.parent), output_dir=str(transcript_file.parent))
    success = processor.update_bunny_transcript(
        video_id=video_id,
        library_id=library_id,
        access_key=access_key,
        transcript_path=str(transcript_file),
        language=language,
    )

    if success:
        console.print(f"[green]✓ Captions uploaded to Bunny.net![/]")
    else:
        console.print(f"[bold red]Error:[/] Failed to upload transcript to Bunny.net")
        sys.exit(1)


def cmd_bunny_chapters(args: argparse.Namespace) -> None:
    """Upload chapter metadata to an existing Bunny.net video."""
    video_id = args.video_id or os.getenv("BUNNY_VIDEO_ID")
    if not video_id:
        video_id = ask_required_text("Bunny Video ID")

    library_id = args.bunny_library_id or os.getenv("BUNNY_LIBRARY_ID")
    if not library_id:
        library_id = ask_optional_text("Bunny Library ID", None)

    access_key = args.bunny_access_key or os.getenv("BUNNY_ACCESS_KEY")
    if not access_key:
        access_key = ask_optional_text("Bunny Access Key", None)

    if not library_id or not access_key:
        console.print(f"[bold red]Error:[/] BUNNY_LIBRARY_ID and BUNNY_ACCESS_KEY are required")
        sys.exit(1)

    chapters_path = args.chapters_path
    if chapters_path:
        chapters_path = normalize_path(chapters_path)
    else:
        chapters_path = ask_required_path("Path to chapters JSON file")

    chapters_file = Path(chapters_path).expanduser().resolve()
    if not chapters_file.exists() or not chapters_file.is_file():
        console.print(f"[bold red]Error:[/] Invalid chapters file: {chapters_path}")
        sys.exit(1)

    try:
        with open(chapters_file, "r", encoding="utf-8") as handle:
            raw_data = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        console.print(f"[bold red]Error:[/] Unable to read chapters file: {exc}")
        sys.exit(1)

    def _coerce_chapters(data: object) -> Optional[List[Dict[str, str]]]:
        def _collect_dicts(items: Sequence[object]) -> List[Dict[str, str]]:
            collected: List[Dict[str, str]] = []
            for item in items:
                if isinstance(item, dict):
                    collected.append(cast(Dict[str, str], item))
            return collected

        if isinstance(data, list):
            if data and isinstance(data[0], dict) and "timestamps" in data[0]:
                timestamps = data[0].get("timestamps")
                if isinstance(timestamps, list):
                    filtered = _collect_dicts(timestamps)
                    return filtered or None
                return None
            filtered = _collect_dicts(data)
            return filtered or None
        if isinstance(data, dict):
            for key in ("chapters", "timestamps"):
                value = data.get(key)
                if isinstance(value, list):
                    filtered = _collect_dicts(value)
                    return filtered or None
            if all(key in data for key in ("title", "start", "end")):
                return [cast(Dict[str, str], data)]
        return None

    chapters_payload = _coerce_chapters(raw_data)
    if not chapters_payload:
        console.print("[bold red]Error:[/] Unable to determine chapter structure from file.")
        sys.exit(1)

    console.print(f"[cyan]Uploading chapters to Bunny.net...[/]")
    console.print(f"  Chapters file: {chapters_file}")
    console.print(f"  Video ID: {video_id}\n")

    processor = VideoProcessor(str(chapters_file.parent))
    success = processor.update_bunny_chapters(
        video_id=video_id,
        library_id=library_id,
        access_key=access_key,
        chapters=chapters_payload,
    )

    if success:
        console.print(f"[green]✓ Chapters uploaded to Bunny.net![/]")
    else:
        console.print(f"[bold red]Error:[/] Failed to upload chapters to Bunny.net")
        sys.exit(1)


def create_parser() -> argparse.ArgumentParser:
    """Create the main argument parser with subcommands."""
    parser = argparse.ArgumentParser(
        description="Video processing toolkit - run individual tools or entire sequences",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Silence removal command
    silence_parser = subparsers.add_parser(
        "silence-removal",
        help="Remove silences from videos"
    )
    silence_parser.add_argument(
        "--input-dir",
        help="Input directory containing videos"
    )
    silence_parser.add_argument(
        "--output-dir",
        help="Output directory (default: input_dir/output)"
    )

    # Concatenation command
    concat_parser = subparsers.add_parser(
        "concat",
        help="Concatenate videos"
    )
    concat_parser.add_argument(
        "--input-dir",
        help="Input directory containing videos to concatenate"
    )
    concat_parser.add_argument(
        "--output-path",
        help="Full path for the output video file (default: input_dir/output/concatenated.mp4)"
    )
    concat_parser.add_argument(
        "--fast-concat",
        action="store_true",
        help="Use fast concatenation (skip reprocessing)"
    )

    # Timestamps command
    timestamps_parser = subparsers.add_parser(
        "timestamps",
        help="Generate timestamps for videos"
    )
    timestamps_parser.add_argument(
        "--input-dir",
        help="Input directory containing videos or a single MP4 video path"
    )
    timestamps_parser.add_argument(
        "--output-path",
        help="Full path for the output JSON file (default: input_dir/output/timestamps.json)"
    )
    timestamps_parser.add_argument(
        "--stamps-from-transcript",
        nargs="?",
        const="",
        help="Generate timestamps from a transcript (optionally provide the transcript path; omit to auto-generate)",
    )
    timestamps_parser.add_argument(
        "--granularity",
        choices=["low", "medium", "high"],
        help="Granularity of generated chapters (low/medium/high)",
    )
    timestamps_parser.add_argument(
        "--timestamp-notes",
        help="Additional instructions for timestamp generation",
    )

    # Transcript command
    transcript_parser = subparsers.add_parser(
        "transcript",
        help="Generate transcript for a video"
    )
    transcript_parser.add_argument(
        "--video-path",
        help="Path to video file"
    )
    transcript_parser.add_argument(
        "--output-path",
        help="Full path for the output VTT file (default: video_dir/output/transcript.vtt)"
    )

    # Context cards command
    context_parser = subparsers.add_parser(
        "context-cards",
        help="Generate context cards from transcript"
    )
    context_parser.add_argument(
        "--input-transcript",
        help="Path to transcript file (.vtt)"
    )
    context_parser.add_argument(
        "--output-path",
        help="Full path for the output context cards file (default: transcript_dir/context-cards.md)"
    )

    # Description command
    desc_parser = subparsers.add_parser(
        "description",
        help="Generate video description from transcript"
    )
    desc_parser.add_argument(
        "--transcript-path",
        help="Path to video transcript (.vtt file)"
    )
    desc_parser.add_argument(
        "--repo-url",
        help="Repository URL to include in description"
    )
    desc_parser.add_argument(
        "--timestamps-path",
        help="Path to timestamps JSON file (optional, omit to generate without timestamps)"
    )
    desc_parser.add_argument(
        "--output-path",
        help="Full path for the output description file (default: transcript_dir/description.md)"
    )

    # SEO command
    seo_parser = subparsers.add_parser(
        "seo",
        help="Generate SEO keywords from transcript"
    )
    seo_parser.add_argument(
        "--transcript-path",
        help="Path to video transcript (.vtt file)"
    )

    # LinkedIn command
    linkedin_parser = subparsers.add_parser(
        "linkedin",
        help="Generate LinkedIn post from transcript"
    )
    linkedin_parser.add_argument(
        "--transcript-path",
        help="Path to video transcript (.vtt file)"
    )
    linkedin_parser.add_argument(
        "--output-path",
        help="Full path for the output LinkedIn post file (default: transcript_dir/linkedin_post.md)"
    )

    # Twitter command
    twitter_parser = subparsers.add_parser(
        "twitter",
        help="Generate Twitter post from transcript"
    )
    twitter_parser.add_argument(
        "--transcript-path",
        help="Path to video transcript (.vtt file)"
    )
    twitter_parser.add_argument(
        "--output-path",
        help="Full path for the output Twitter post file (default: transcript_dir/twitter_post.md)"
    )

    # Bunny video upload command
    bunny_parser = subparsers.add_parser(
        "bunny-video",
        help="Upload video to Bunny.net"
    )
    bunny_parser.add_argument(
        "--video-path",
        help="Path to video file to upload"
    )
    bunny_parser.add_argument(
        "--bunny-library-id",
        help="Bunny.net library ID"
    )
    bunny_parser.add_argument(
        "--bunny-access-key",
        help="Bunny.net access key"
    )
    bunny_parser.add_argument(
        "--bunny-collection-id",
        help="Bunny.net collection ID (optional)"
    )

    # Bunny transcript upload command
    bunny_transcript_parser = subparsers.add_parser(
        "bunny-transcript",
        help="Upload transcript captions to Bunny.net"
    )
    bunny_transcript_parser.add_argument(
        "--video-id",
        help="Existing Bunny.net video ID"
    )
    bunny_transcript_parser.add_argument(
        "--transcript-path",
        help="Path to transcript file (.vtt)"
    )
    bunny_transcript_parser.add_argument(
        "--language",
        help="Caption language code (default: en)"
    )
    bunny_transcript_parser.add_argument(
        "--bunny-library-id",
        help="Bunny.net library ID"
    )
    bunny_transcript_parser.add_argument(
        "--bunny-access-key",
        help="Bunny.net access key"
    )

    # Bunny chapters upload command
    bunny_chapters_parser = subparsers.add_parser(
        "bunny-chapters",
        help="Upload chapters metadata to Bunny.net"
    )
    bunny_chapters_parser.add_argument(
        "--video-id",
        help="Existing Bunny.net video ID"
    )
    bunny_chapters_parser.add_argument(
        "--chapters-path",
        help="Path to chapters JSON file (e.g. timestamps.json)"
    )
    bunny_chapters_parser.add_argument(
        "--bunny-library-id",
        help="Bunny.net library ID"
    )
    bunny_chapters_parser.add_argument(
        "--bunny-access-key",
        help="Bunny.net access key"
    )

    return parser


def main() -> None:
    """Main CLI entry point."""
    load_dotenv()

    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Validate environment
    commands_without_ai = {"bunny-video", "bunny-transcript", "bunny-chapters"}
    if args.command not in commands_without_ai:
        missing = [var for var in ("OPENAI_API_KEY", "GROQ_API_KEY") if not os.getenv(var)]
        if missing:
            missing_list = ", ".join(missing)
            console.print(
                f"[bold red]Missing required environment variables:[/] {missing_list}"
            )
            sys.exit(1)

    # Route to appropriate command handler
    command_handlers = {
        "silence-removal": cmd_silence_removal,
        "concat": cmd_concat,
        "timestamps": cmd_timestamps,
        "transcript": cmd_transcript,
        "context-cards": cmd_context_cards,
        "description": cmd_description,
        "seo": cmd_seo,
        "linkedin": cmd_linkedin,
        "twitter": cmd_twitter,
        "bunny-video": cmd_bunny_video,
        "bunny-transcript": cmd_bunny_transcript,
        "bunny-chapters": cmd_bunny_chapters,
    }

    handler = command_handlers.get(args.command)
    if handler:
        try:
            handler(args)
        except KeyboardInterrupt:
            console.print("\n[bold yellow]Interrupted by user.[/]")
            sys.exit(130)
        except Exception as exc:
            console.print(f"[bold red]Error:[/] {exc}")
            sys.exit(1)
    else:
        console.print(f"[bold red]Unknown command:[/] {args.command}")
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
