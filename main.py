"""Compatibility CLI for orchestrating the legacy video-tool workflow.

This module preserves the original interactive entry point relied upon by the
integration tests while delegating modern, feature-rich commands to
``video_tool.cli``. Use ``video_tool.cli`` directly for new development.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from typing import Dict, List, Optional

from rich.console import Console

from video_tool import VideoProcessor
from video_tool.cli import main as cli_main, normalize_path

console = Console()


@dataclass(frozen=True)
class StepFlagSpec:
    """Represents a boolean flag that controls whether a step is skipped."""

    attr: str
    prompt: str


STEP_FLAG_SPECS: List[StepFlagSpec] = [
    StepFlagSpec("skip_silence_removal", "Skip silence removal? (y/n): "),
    StepFlagSpec("skip_concat", "Skip concatenation? (y/n): "),
    StepFlagSpec("skip_reprocessing", "Use fast concatenation (skip reprocessing)? (y/n): "),
    StepFlagSpec("skip_timestamps", "Skip timestamp generation? (y/n): "),
    StepFlagSpec("skip_transcript", "Skip transcript generation? (y/n): "),
    StepFlagSpec("skip_context_cards", "Skip context card generation? (y/n): "),
    StepFlagSpec("skip_description", "Skip description generation? (y/n): "),
    StepFlagSpec("skip_seo", "Skip SEO keyword generation? (y/n): "),
    StepFlagSpec("skip_linkedin", "Skip LinkedIn post generation? (y/n): "),
    StepFlagSpec("skip_twitter", "Skip Twitter post generation? (y/n): "),
    StepFlagSpec("skip_bunny_video_upload", "Skip Bunny video upload? (y/n): "),
    StepFlagSpec("skip_bunny_chapter_upload", "Skip Bunny chapter upload? (y/n): "),
    StepFlagSpec("skip_bunny_transcript_upload", "Skip Bunny transcript upload? (y/n): "),
]


def _prompt_bool(prompt_text: str) -> bool:
    """Return ``True`` when the user responds with ``y``/``yes``."""

    response = input(prompt_text).strip().lower()
    return response in {"y", "yes"}


def get_user_input() -> Dict[str, object]:
    """Collect interactive parameters for running the processing pipeline."""

    input_dir = normalize_path(
        input("Enter the path to the directory containing the videos: ").strip()
    )
    repo_url = input("Enter the GitHub repository URL (optional): ").strip() or None
    video_title = input("Enter the video title (optional): ").strip() or None

    skip_silence_removal = _prompt_bool(STEP_FLAG_SPECS[0].prompt)
    skip_concat = _prompt_bool(STEP_FLAG_SPECS[1].prompt)

    if skip_concat:
        skip_reprocessing = False
    else:
        skip_reprocessing = _prompt_bool(STEP_FLAG_SPECS[2].prompt)

    skip_timestamps = _prompt_bool(STEP_FLAG_SPECS[3].prompt)
    skip_transcript = _prompt_bool(STEP_FLAG_SPECS[4].prompt)
    skip_context_cards = _prompt_bool(STEP_FLAG_SPECS[5].prompt)
    skip_description = _prompt_bool(STEP_FLAG_SPECS[6].prompt)
    skip_seo = _prompt_bool(STEP_FLAG_SPECS[7].prompt)
    skip_linkedin = _prompt_bool(STEP_FLAG_SPECS[8].prompt)
    skip_twitter = _prompt_bool(STEP_FLAG_SPECS[9].prompt)
    skip_bunny_video_upload = _prompt_bool(STEP_FLAG_SPECS[10].prompt)
    skip_bunny_chapter_upload = _prompt_bool(STEP_FLAG_SPECS[11].prompt)
    skip_bunny_transcript_upload = _prompt_bool(STEP_FLAG_SPECS[12].prompt)

    bunny_library_id = None
    bunny_collection_id = None
    bunny_caption_language = "en"

    if not skip_bunny_video_upload:
        bunny_library_id = input("Enter Bunny library ID: ").strip() or None
        bunny_collection_id = input("Enter Bunny collection ID (optional): ").strip() or None
        bunny_caption_language = input("Enter Bunny caption language (default: en): ").strip() or "en"

    bunny_video_id = None
    verbose_logging = _prompt_bool("Enable verbose logging? (y/n): ")

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
    """Parse legacy CLI arguments for integration compatibility."""

    parser = argparse.ArgumentParser(description="Legacy video-tool runner")
    parser.add_argument("--manual", action="store_true", help="Run interactively")
    parser.add_argument("--command", default="run")
    parser.add_argument("--profile")
    parser.add_argument("--input-dir")
    parser.add_argument("--repo-url")
    parser.add_argument("--video-title")
    parser.add_argument("--all", action="store_true", help="Run all steps")

    parser.add_argument("--concat", action="store_true")
    parser.add_argument("--transcript", action="store_true")
    parser.add_argument("--fast-concat", dest="fast_concat", action="store_true")
    parser.add_argument("--standard-concat", dest="standard_concat", action="store_true")

    parser.add_argument("--bunny-video-path")
    parser.add_argument("--bunny-transcript-path")
    parser.add_argument("--bunny-chapters-path")

    for spec in STEP_FLAG_SPECS:
        parser.add_argument(f"--{spec.attr}", action="store_true", default=False)

    return parser.parse_args()


def _run_manual(params: Dict[str, object]) -> None:
    """Execute the pipeline using manually supplied parameters."""

    processor = VideoProcessor(
        params["input_dir"],
        video_title=params.get("video_title"),
        show_external_logs=bool(params.get("verbose_logging", False)),
    )

    output_video: Optional[str] = None

    if not params.get("skip_silence_removal", True):
        processor.remove_silences()

    if not params.get("skip_timestamps", True):
        processor.generate_timestamps()

    if not params.get("skip_concat", True):
        concat_result = processor.concatenate_videos(
            skip_reprocessing=bool(params.get("skip_reprocessing", True))
        )
        if isinstance(concat_result, str):
            output_video = concat_result
        else:
            console.print("[yellow]Video concatenation completed but no output file returned[/]")

    if not output_video:
        output_video = str(processor.output_dir / "final.mp4")

    transcript_path = str(processor.output_dir / "transcript.vtt")

    if not params.get("skip_transcript", True):
        processor.generate_transcript(output_video)

    if not params.get("skip_context_cards", True):
        processor.generate_context_cards(transcript_path)

    description_path: Optional[str] = None
    if not params.get("skip_description", True) and params.get("repo_url"):
        description_path = processor.generate_description(
            output_video, params["repo_url"], transcript_path
        )

    if not params.get("skip_seo", True) and description_path:
        processor.generate_seo_keywords(description_path)

    if not params.get("skip_linkedin", True):
        processor.generate_linkedin_post(transcript_path)

    if not params.get("skip_twitter", True):
        processor.generate_twitter_post(transcript_path)

    if not (
        params.get("skip_bunny_video_upload", True)
        and params.get("skip_bunny_chapter_upload", True)
        and params.get("skip_bunny_transcript_upload", True)
    ):
        processor.deploy_to_bunny(
            output_video,
            upload_video=not params.get("skip_bunny_video_upload", True),
            upload_chapters=not params.get("skip_bunny_chapter_upload", True),
            upload_transcript=not params.get("skip_bunny_transcript_upload", True),
            library_id=params.get("bunny_library_id"),
            collection_id=params.get("bunny_collection_id"),
            video_title=params.get("video_title"),
            chapters=[],
            transcript_path=transcript_path,
            caption_language=params.get("bunny_caption_language", "en"),
            video_id=params.get("bunny_video_id"),
        )


def _run_cli(args: argparse.Namespace) -> None:
    """Handle non-interactive invocations that specify individual steps."""

    transcript_requested = getattr(args, "transcript", False)
    concat_requested = getattr(args, "concat", False)
    input_dir = normalize_path(args.input_dir) if args.input_dir else None

    if transcript_requested:
        if not input_dir:
            console.print(
                "[bold red]Input directory required.[/] "
                "Provide it to continue running Transcript."
            )
            return
        processor = VideoProcessor(input_dir)
        video_path = str(processor.output_dir / "final.mp4")
        processor.generate_transcript(video_path)
        return

    if concat_requested:
        if not input_dir:
            console.print(
                "[bold red]Input directory required for concatenation.[/]"
            )
            return
        processor = VideoProcessor(input_dir)
        concat_result = processor.concatenate_videos(
            skip_reprocessing=bool(args.fast_concat)
        )
        if not isinstance(concat_result, str):
            console.print(
                "[yellow]Video concatenation completed but no output file returned[/]"
            )
        return

    # Fallback to the modern CLI for other commands
    cli_main()


def main() -> None:
    """Primary entry point for the compatibility CLI."""

    args = parse_cli_args()

    if args.command != "run":
        cli_main()
        return

    if args.manual:
        params = get_user_input()
        _run_manual(params)
        return

    _run_cli(args)


if __name__ == "__main__":
    main()
