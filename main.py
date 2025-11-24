"""
Interactive and non-interactive entry point for the video-tool workflow pipeline.

This module maintains a lightweight orchestration layer used by the legacy
integration tests. For the full feature set, prefer `video_tool.cli`.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from rich.console import Console

from video_tool import VideoProcessor

console = Console()


@dataclass(frozen=True)
class StepFlagSpec:
    attr: str
    prompt: str


STEP_FLAG_SPECS: List[StepFlagSpec] = [
    StepFlagSpec("skip_silence_removal", "Skip silence removal? (y/n)"),
    StepFlagSpec("skip_concat", "Skip concatenation? (y/n)"),
    StepFlagSpec("skip_reprocessing", "Skip reprocessing during concat (fast mode)? (y/n)"),
    StepFlagSpec("skip_timestamps", "Skip timestamp generation? (y/n)"),
    StepFlagSpec("skip_transcript", "Skip transcript generation? (y/n)"),
    StepFlagSpec("skip_context_cards", "Skip context cards? (y/n)"),
    StepFlagSpec("skip_description", "Skip description generation? (y/n)"),
    StepFlagSpec("skip_seo", "Skip SEO keywords? (y/n)"),
    StepFlagSpec("skip_linkedin", "Skip LinkedIn post? (y/n)"),
    StepFlagSpec("skip_twitter", "Skip Twitter post? (y/n)"),
    StepFlagSpec("skip_bunny_video_upload", "Skip Bunny video upload? (y/n)"),
    StepFlagSpec("skip_bunny_chapter_upload", "Skip Bunny chapter upload? (y/n)"),
    StepFlagSpec("skip_bunny_transcript_upload", "Skip Bunny transcript upload? (y/n)"),
]


def _normalize_path(raw: str) -> str:
    """Normalize shell-like path input."""
    trimmed = raw.strip()
    if (trimmed.startswith('"') and trimmed.endswith('"')) or (
        trimmed.startswith("'") and trimmed.endswith("'")
    ):
        trimmed = trimmed[1:-1]
    trimmed = trimmed.replace("\\ ", " ")
    return str(Path(trimmed).expanduser())


def _ask_boolean(prompt: str, default: bool = False) -> bool:
    """Prompt for a yes/no response."""
    default_str = "y" if default else "n"
    while True:
        response = input(prompt + " ").strip().lower()
        if not response:
            response = default_str
        if response in ("y", "yes"):
            return True
        if response in ("n", "no"):
            return False
        console.print("[yellow]Please answer with 'y' or 'n'.[/]")


def get_user_input() -> Dict[str, object]:
    """Collect interactive parameters for the pipeline."""
    input_dir = _normalize_path(input("Input directory: ").strip())
    repo_url_raw = input("Repository URL (optional): ").strip()
    repo_url = repo_url_raw or None
    video_title_raw = input("Video title (optional): ").strip()
    video_title = video_title_raw or None

    # Silence removal and concat toggles
    skip_silence_removal = _ask_boolean(STEP_FLAG_SPECS[0].prompt, default=False)
    skip_concat = _ask_boolean(STEP_FLAG_SPECS[1].prompt, default=False)
    if not skip_concat:
        skip_reprocessing = _ask_boolean(STEP_FLAG_SPECS[2].prompt, default=False)
    else:
        skip_reprocessing = False

    # Remaining toggles
    skip_timestamps = _ask_boolean(STEP_FLAG_SPECS[3].prompt, default=False)
    skip_transcript = _ask_boolean(STEP_FLAG_SPECS[4].prompt, default=False)
    skip_context_cards = _ask_boolean(STEP_FLAG_SPECS[5].prompt, default=False)
    skip_description = _ask_boolean(STEP_FLAG_SPECS[6].prompt, default=False)
    skip_seo = _ask_boolean(STEP_FLAG_SPECS[7].prompt, default=False)
    skip_linkedin = _ask_boolean(STEP_FLAG_SPECS[8].prompt, default=False)
    skip_twitter = _ask_boolean(STEP_FLAG_SPECS[9].prompt, default=False)
    skip_bunny_video_upload = _ask_boolean(STEP_FLAG_SPECS[10].prompt, default=False)
    skip_bunny_chapter_upload = _ask_boolean(STEP_FLAG_SPECS[11].prompt, default=False)
    skip_bunny_transcript_upload = _ask_boolean(STEP_FLAG_SPECS[12].prompt, default=False)

    bunny_library_id = None
    bunny_collection_id = None
    bunny_video_id = None
    bunny_caption_language = "en"

    if not skip_bunny_video_upload:
        bunny_library_id = input("Bunny Library ID: ").strip() or None
        bunny_collection_id = input("Bunny Collection ID (optional): ").strip() or None
    if not skip_bunny_transcript_upload:
        bunny_caption_language = input("Bunny caption language (default: en): ").strip() or "en"

    verbose_logging = _ask_boolean("Enable verbose logging? (y/n)", default=False)

    return {
        "input_dir": input_dir,
        "repo_url": repo_url,
        "video_title": video_title,
        "skip_silence_removal": skip_silence_removal,
        "skip_concat": skip_concat,
        "skip_reprocessing": skip_reprocessing,
        "skip_timestamps": skip_timestamps,
        "skip_transcript": skip_transcript,
        "skip_context_cards": skip_context_cards,
        "skip_description": skip_description,
        "skip_seo": skip_seo,
        "skip_linkedin": skip_linkedin,
        "skip_twitter": skip_twitter,
        "skip_bunny_video_upload": skip_bunny_video_upload,
        "skip_bunny_chapter_upload": skip_bunny_chapter_upload,
        "skip_bunny_transcript_upload": skip_bunny_transcript_upload,
        "bunny_library_id": bunny_library_id,
        "bunny_collection_id": bunny_collection_id,
        "bunny_caption_language": bunny_caption_language,
        "bunny_video_id": bunny_video_id,
        "verbose_logging": verbose_logging,
    }


def parse_cli_args() -> argparse.Namespace:
    """Parse CLI arguments for selective command execution."""
    parser = argparse.ArgumentParser(description="video-tool legacy runner")
    parser.add_argument("--manual", action="store_true", help="Run in interactive/manual mode")
    parser.add_argument("--all", action="store_true", help="Run all steps non-interactively")
    parser.add_argument("--input-dir", help="Input directory containing videos")
    parser.add_argument("--concat", action="store_true", help="Only run concatenation")
    parser.add_argument("--fast-concat", action="store_true", help="Use fast concatenation")
    parser.add_argument("--transcript", action="store_true", help="Only run transcript generation")
    parser.add_argument("--timestamps", action="store_true", help="Only run timestamp generation")
    parser.add_argument("--context-cards", action="store_true", help="Only run context cards")
    parser.add_argument("--description", action="store_true", help="Only run description")
    parser.add_argument("--seo", action="store_true", help="Only run SEO keywords")
    parser.add_argument("--linkedin", action="store_true", help="Only run LinkedIn post")
    parser.add_argument("--twitter", action="store_true", help="Only run Twitter post")
    parser.add_argument("--bunny-video", action="store_true", help="Only upload video to Bunny.net")
    parser.add_argument("--bunny-transcript", action="store_true", help="Only upload transcript to Bunny.net")
    parser.add_argument("--bunny-chapters", action="store_true", help="Only upload chapters to Bunny.net")
    parser.add_argument("--profile", help="Execution profile (unused placeholder)")

    # Step flags for non-interactive passes
    for spec in STEP_FLAG_SPECS:
        parser.add_argument(f"--{spec.attr.replace('_', '-')}", action="store_true")

    return parser.parse_args()


def _build_processor(input_dir: str, video_title: Optional[str], verbose_logging: bool) -> VideoProcessor:
    return VideoProcessor(input_dir, video_title=video_title, show_external_logs=verbose_logging)


def _run_full_pipeline(params: Dict[str, object]) -> None:
    processor = _build_processor(
        params["input_dir"],
        params.get("video_title"),
        params.get("verbose_logging", False),
    )

    concat_output: Optional[str] = None
    transcript_path: Optional[str] = None

    if not params.get("skip_silence_removal", False):
        processor.remove_silences()

    if not params.get("skip_timestamps", False):
        processor.generate_timestamps()

    if not params.get("skip_concat", False):
        concat_output = processor.concatenate_videos(
            skip_reprocessing=params.get("skip_reprocessing", False)
        )

    video_path = (
        concat_output
        if isinstance(concat_output, str)
        else str(Path(processor.output_dir) / "final.mp4")
    )

    if not params.get("skip_transcript", False):
        transcript_path = processor.generate_transcript(video_path)

    transcript_path = transcript_path or str(Path(processor.output_dir) / "transcript.vtt")

    if not params.get("skip_context_cards", False):
        processor.generate_context_cards(transcript_path, output_path=None)

    if not params.get("skip_description", False) and params.get("repo_url"):
        description_path = processor.generate_description(
            video_path,
            params["repo_url"],
            transcript_path,
        )
        if not params.get("skip_seo", False):
            processor.generate_seo_keywords(description_path)

    if not params.get("skip_linkedin", False):
        processor.generate_linkedin_post(transcript_path)

    if not params.get("skip_twitter", False):
        processor.generate_twitter_post(transcript_path)

    upload_video = not params.get("skip_bunny_video_upload", False)
    upload_chapters = not params.get("skip_bunny_chapter_upload", False)
    upload_transcript = not params.get("skip_bunny_transcript_upload", False)

    if upload_video or upload_chapters or upload_transcript:
        processor.deploy_to_bunny(
            video_path,
            upload_video=upload_video,
            upload_chapters=upload_chapters,
            upload_transcript=upload_transcript,
            library_id=params.get("bunny_library_id"),
            collection_id=params.get("bunny_collection_id"),
            video_title=params.get("video_title"),
            chapters=[],
            transcript_path=transcript_path,
            caption_language=params.get("bunny_caption_language", "en"),
            video_id=params.get("bunny_video_id"),
        )


def _run_single_step(args: argparse.Namespace) -> None:
    """Handle non-interactive single-step execution."""
    if args.transcript:
        if not args.input_dir:
            console.print(
                "[bold red]Input directory required.[/] "
                "Provide it to continue running Transcript."
            )
            return
        processor = _build_processor(args.input_dir, None, False)
        video_path = str(Path(processor.output_dir) / "final.mp4")
        processor.generate_transcript(video_path)
        return

    if args.concat:
        if not args.input_dir:
            console.print("[bold red]Input directory required for concatenation.[/]")
            return
        processor = _build_processor(args.input_dir, None, False)
        result = processor.concatenate_videos(skip_reprocessing=args.fast_concat)
        if not isinstance(result, str):
            console.print(
                "[yellow]Video concatenation completed but no output file returned[/]"
            )
        return

    # Default fallback to full pipeline in non-interactive mode
    params = {
        "input_dir": args.input_dir or "",
        "repo_url": None,
        "video_title": None,
        "skip_silence_removal": False,
        "skip_concat": not args.concat and not args.all,
        "skip_reprocessing": args.fast_concat,
        "skip_timestamps": not args.timestamps and not args.all,
        "skip_transcript": not args.transcript and not args.all,
        "skip_context_cards": not args.context_cards and not args.all,
        "skip_description": not args.description and not args.all,
        "skip_seo": not args.seo and not args.all,
        "skip_linkedin": not args.linkedin and not args.all,
        "skip_twitter": not args.twitter and not args.all,
        "skip_bunny_video_upload": not args.bunny_video and not args.all,
        "skip_bunny_chapter_upload": not args.bunny_chapters and not args.all,
        "skip_bunny_transcript_upload": not args.bunny_transcript and not args.all,
        "bunny_library_id": None,
        "bunny_collection_id": None,
        "bunny_caption_language": "en",
        "bunny_video_id": None,
        "verbose_logging": False,
    }
    _run_full_pipeline(params)


def main() -> None:
    args = parse_cli_args()

    single_step_flags = [
        args.concat,
        args.transcript,
        args.timestamps,
        args.context_cards,
        args.description,
        args.seo,
        args.linkedin,
        args.twitter,
        args.bunny_video,
        args.bunny_transcript,
        args.bunny_chapters,
    ]

    if args.manual or (not any(single_step_flags) and not args.all):
        params = get_user_input()
        _run_full_pipeline(params)
    else:
        _run_single_step(args)


if __name__ == "__main__":
    main()
