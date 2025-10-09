"""
Command-line interface for video-tool.

Each tool can be called independently with its own arguments.
If arguments are not provided, the user will be prompted interactively.
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Optional

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

    # Handle output directory
    output_dir = None
    if args.output_dir:
        output_dir = normalize_path(args.output_dir)

    skip_reprocessing = args.fast_concat if args.fast_concat is not None else False

    console.print(f"[cyan]Running video concatenation...[/]")
    console.print(f"  Input: {input_path}")
    console.print(f"  Output: {output_dir or str(input_path / 'output')}")
    console.print(f"  Fast mode: {'Yes' if skip_reprocessing else 'No'}\n")

    processor = VideoProcessor(str(input_path), output_dir=output_dir)
    output_video = processor.concatenate_videos(skip_reprocessing=skip_reprocessing)

    console.print(f"[green]✓ Concatenation complete![/]")
    console.print(f"  Output video: {output_video}")


def cmd_timestamps(args: argparse.Namespace) -> None:
    """Generate timestamps for videos."""
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

    console.print(f"[cyan]Generating timestamps...[/]")
    console.print(f"  Input: {input_path}")
    console.print(f"  Output: {output_dir or str(input_path / 'output')}\n")

    processor = VideoProcessor(str(input_path), output_dir=output_dir)
    timestamps_info = processor.generate_timestamps()

    console.print(f"[green]✓ Timestamps generated![/]")
    console.print(f"  Timestamps file: {processor.output_dir}/timestamps.json")


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

    console.print(f"[cyan]Generating transcript...[/]")
    console.print(f"  Video: {video_file}\n")

    # Use the video's parent directory as input_dir
    processor = VideoProcessor(str(video_file.parent))
    transcript_path = processor.generate_transcript(str(video_file))

    console.print(f"[green]✓ Transcript generated![/]")
    console.print(f"  Transcript: {transcript_path}")


def cmd_context_cards(args: argparse.Namespace) -> None:
    """Generate context cards from transcript."""
    video_path = args.video_path
    if not video_path:
        video_path = ask_required_path("Path to video file")
    else:
        video_path = normalize_path(video_path)

    video_file = Path(video_path).expanduser().resolve()
    if not video_file.exists() or not video_file.is_file():
        console.print(f"[bold red]Error:[/] Invalid video file: {video_path}")
        sys.exit(1)

    console.print(f"[cyan]Generating context cards...[/]")
    console.print(f"  Video: {video_file}\n")

    processor = VideoProcessor(str(video_file.parent))

    # First, check if transcript exists
    transcript_path = processor.output_dir / "transcript.vtt"
    if not transcript_path.exists():
        console.print(f"[yellow]Transcript not found. Generating transcript first...[/]")
        transcript_path_str = processor.generate_transcript(str(video_file))
        transcript_path = Path(transcript_path_str)

    cards_path = processor.generate_context_cards(str(transcript_path))

    console.print(f"[green]✓ Context cards generated![/]")
    console.print(f"  Context cards: {cards_path}")


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

    repo_url = args.repo_url
    if not repo_url:
        repo_url = ask_optional_text("Repository URL", None)

    console.print(f"[cyan]Generating description...[/]")
    console.print(f"  Transcript: {transcript_file}")
    console.print(f"  Repository: {repo_url or 'None'}\n")

    processor = VideoProcessor(str(transcript_file.parent.parent))

    # Find the video file (assume it's in the parent directory or output directory)
    video_candidates = list(transcript_file.parent.parent.glob("*.mp4"))
    video_candidates += list(transcript_file.parent.glob("*.mp4"))

    if not video_candidates:
        console.print(f"[bold red]Error:[/] No video file found near transcript")
        sys.exit(1)

    video_path = str(video_candidates[0])

    description_path = processor.generate_description(
        video_path=video_path,
        repo_url=repo_url,
        transcript_path=str(transcript_file)
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

    console.print(f"[cyan]Generating SEO keywords...[/]")
    console.print(f"  Transcript: {transcript_file}\n")

    processor = VideoProcessor(str(transcript_file.parent.parent))

    # First generate description if it doesn't exist
    description_path = transcript_file.parent / "description.md"
    if not description_path.exists():
        console.print(f"[yellow]Description not found. Generating description first...[/]")

        # Find video file
        video_candidates = list(transcript_file.parent.parent.glob("*.mp4"))
        video_candidates += list(transcript_file.parent.glob("*.mp4"))

        if not video_candidates:
            console.print(f"[bold red]Error:[/] No video file found near transcript")
            sys.exit(1)

        video_path = str(video_candidates[0])
        description_path = processor.generate_description(
            video_path=video_path,
            transcript_path=str(transcript_file)
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

    console.print(f"[cyan]Generating LinkedIn post...[/]")
    console.print(f"  Transcript: {transcript_file}\n")

    processor = VideoProcessor(str(transcript_file.parent.parent))
    linkedin_path = processor.generate_linkedin_post(str(transcript_file))

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

    console.print(f"[cyan]Generating Twitter post...[/]")
    console.print(f"  Transcript: {transcript_file}\n")

    processor = VideoProcessor(str(transcript_file.parent.parent))
    twitter_path = processor.generate_twitter_post(str(transcript_file))

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
    caption_language = args.bunny_caption_language or os.getenv("BUNNY_CAPTION_LANGUAGE") or "en"

    console.print(f"[cyan]Uploading video to Bunny.net...[/]")
    console.print(f"  Video: {video_file}")
    console.print(f"  Library ID: {library_id}\n")

    processor = VideoProcessor(str(video_file.parent))
    result = processor.deploy_to_bunny(
        video_path=str(video_file),
        upload_video=True,
        upload_chapters=False,
        upload_transcript=False,
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
        "--output-dir",
        help="Output directory (default: input_dir/output)"
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
        help="Input directory containing videos"
    )
    timestamps_parser.add_argument(
        "--output-dir",
        help="Output directory (default: input_dir/output)"
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

    # Context cards command
    context_parser = subparsers.add_parser(
        "context-cards",
        help="Generate context cards from video"
    )
    context_parser.add_argument(
        "--video-path",
        help="Path to video file"
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

    # Twitter command
    twitter_parser = subparsers.add_parser(
        "twitter",
        help="Generate Twitter post from transcript"
    )
    twitter_parser.add_argument(
        "--transcript-path",
        help="Path to video transcript (.vtt file)"
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
    bunny_parser.add_argument(
        "--bunny-caption-language",
        default="en",
        help="Caption language code (default: en)"
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
    if args.command != "bunny-video":
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
