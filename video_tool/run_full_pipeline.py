"""Orchestrate the full video-tool workflow for a directory of clips.

This module is packaged with the library so the ``video-tool pipeline`` command
works in both editable checkouts and regular wheel installs.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import NamedTuple

from dotenv import load_dotenv


def _load_env() -> None:
    """Load environment variables from common locations."""
    # First, respect any .env in the current working directory.
    load_dotenv()

    # Also try a project-level .env (useful when running from a repo checkout).
    project_env = Path(__file__).resolve().parent.parent / ".env"
    if project_env.exists():
        load_dotenv(project_env)


_load_env()

REQUIRED_AI_VARS = ("OPENAI_API_KEY", "GROQ_API_KEY")


class PipelineConfig(NamedTuple):
    """Collected, non-interactive configuration for the pipeline run."""

    input_dir: Path
    output_dir: Path
    cli_bin: str
    concat_title: str
    fast_concat: bool
    concat_output_path: Path | None
    timestamps_output_path: Path
    timestamps_granularity: str
    timestamp_notes: str
    transcript_output_path: Path
    include_context_cards: bool
    context_cards_output_path: Path
    include_linkedin: bool
    linkedin_output_path: Path
    include_seo: bool
    include_twitter: bool
    twitter_output_path: Path
    upload_bunny: bool
    bunny_library_id: str | None
    bunny_access_key: str | None
    bunny_collection_id: str | None
    metadata_path: Path


def require_env_vars(
    needs_bunny: bool,
    bunny_library_id: str | None = None,
    bunny_access_key: str | None = None,
) -> None:
    """Ensure required environment variables are present for the selected steps."""
    missing = [name for name in REQUIRED_AI_VARS if not os.getenv(name)]

    if needs_bunny:
        if not (os.getenv("BUNNY_LIBRARY_ID") or bunny_library_id):
            missing.append("BUNNY_LIBRARY_ID")
        if not (os.getenv("BUNNY_ACCESS_KEY") or bunny_access_key):
            missing.append("BUNNY_ACCESS_KEY")

    if missing:
        formatted = ", ".join(missing)
        raise SystemExit(f"Missing required environment variables: {formatted}")


def prompt_input_directory() -> Path:
    """Prompt the user for the input directory containing video clips."""
    while True:
        try:
            answer = input("Enter the path to the directory containing your video clips: ").strip()
        except EOFError:
            raise SystemExit("No input directory provided.")

        if not answer:
            print("Please provide a valid directory path.")
            continue

        # Remove quotes if present (handles both single and double quotes)
        if (answer.startswith('"') and answer.endswith('"')) or (answer.startswith("'") and answer.endswith("'")):
            answer = answer[1:-1]

        # Handle shell-style escaping by replacing escaped spaces
        answer = answer.replace("\\ ", " ")

        input_dir = Path(answer).expanduser().resolve()
        if not input_dir.exists():
            print(f"Directory '{input_dir}' does not exist. Please try again.")
            print("Tip: You can use quotes around the path or escape spaces with backslashes.")
            continue

        if not input_dir.is_dir():
            print(f"'{input_dir}' is not a directory. Please try again.")
            continue

        return input_dir


def prompt_yes_no(question: str, default: bool = False) -> bool:
    """Prompt for a yes/no answer with a default."""
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        try:
            answer = input(f"{question} {suffix}: ").strip().lower()
        except EOFError:
            return default

        if not answer:
            return default
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("Please answer with 'y' or 'n'.")


def prompt_non_empty(question: str, default: str | None = None) -> str:
    """Prompt until a non-empty string is provided."""
    while True:
        try:
            answer = input(
                f"{question}" + (f" (default: {default})" if default else "") + ": "
            ).strip()
        except EOFError:
            if default:
                return default
            raise SystemExit("Required input missing.")

        if answer:
            return answer
        if default:
            return default
        print("Please provide a value.")


def normalize_path_str(value: str) -> str:
    """Normalize shell-style path strings (quotes, escaped spaces)."""
    trimmed = value.strip()
    if (trimmed.startswith('"') and trimmed.endswith('"')) or (
        trimmed.startswith("'") and trimmed.endswith("'")
    ):
        trimmed = trimmed[1:-1]
    return trimmed.replace("\\ ", " ")


def prompt_path(question: str, default: Path | None = None, allow_blank: bool = False) -> Path | None:
    """Prompt for a filesystem path, applying shell-style normalization."""
    suffix = f" (default: {default})" if default else ""
    while True:
        try:
            answer = input(f"{question}{suffix}: ").strip()
        except EOFError:
            answer = ""

        if not answer:
            if default is not None:
                return default
            if allow_blank:
                return None
            print("Please provide a path.")
            continue

        normalized = normalize_path_str(answer)
        return Path(normalized).expanduser().resolve()


def run_cli_step(description: str, command: list[str]) -> None:
    """Run a CLI step with a friendly description."""
    print(f"==> {description}...")
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Step '{description}' failed with exit code {exc.returncode}.") from exc
    except FileNotFoundError as exc:
        raise SystemExit(f"Unable to execute command '{command[0]}': {exc}") from exc


def ensure_file(path: Path, description: str) -> None:
    """Verify that an expected file exists."""
    if not path.exists():
        raise SystemExit(f"Expected {description} at '{path}', but it was not found.")


def _resolve_concatenated_video(output_dir: Path) -> Path:
    """Determine the concatenated video path using metadata.json or best effort."""
    metadata_path = output_dir / "metadata.json"
    if metadata_path.exists():
        try:
            with open(metadata_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if isinstance(data, dict):
                output_path = data.get("output_path")
                if output_path:
                    candidate = Path(output_path).expanduser().resolve()
                    if candidate.exists():
                        return candidate
        except (OSError, json.JSONDecodeError):
            # Fall back to best-effort scanning
            pass

    # Fallback: pick the newest MP4 in output_dir
    mp4_candidates = sorted(output_dir.glob("*.mp4"), key=lambda p: p.stat().st_mtime)
    if mp4_candidates:
        return mp4_candidates[-1]

    # Final fallback: the legacy default name
    return output_dir / "concatenated.mp4"


def build_cli(args: argparse.Namespace) -> str:
    """Determine the CLI executable to invoke."""
    cli_bin = args.cli_bin or os.getenv("VIDEO_TOOL_CLI") or "video-tool"
    if shutil.which(cli_bin) is None:
        raise SystemExit(
            f"CLI command '{cli_bin}' is not available. Install video-tool or set --cli-bin."
        )
    return cli_bin


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the full video-tool pipeline for a directory of clips.",
    )
    parser.add_argument(
        "--cli-bin",
        help="Override the video-tool executable (defaults to VIDEO_TOOL_CLI env or 'video-tool')",
    )
    return parser.parse_args(argv)


def gather_pipeline_config(args: argparse.Namespace) -> PipelineConfig:
    """Collect all pipeline inputs up front so individual steps never prompt."""
    input_dir = prompt_input_directory()

    default_output_dir = input_dir / "output"
    output_dir = prompt_path(
        "Output directory for pipeline assets", default=default_output_dir
    )
    assert output_dir is not None  # for type checkers

    concat_title = prompt_non_empty(
        "Title for the concatenated video", default=input_dir.name
    )
    fast_concat = prompt_yes_no("Use fast concatenation", default=False)

    custom_concat_path = prompt_path(
        "Full output path for concatenated video (leave blank for default naming)",
        default=None,
        allow_blank=True,
    )

    print("\nSelect which outputs to generate (all enabled by default):")
    include_context_cards = prompt_yes_no("Generate context cards", default=True)
    include_linkedin = prompt_yes_no("Generate LinkedIn post", default=True)
    include_twitter = prompt_yes_no("Generate Twitter post", default=True)
    include_seo = prompt_yes_no("Generate SEO keywords", default=True)
    upload_bunny = prompt_yes_no("Upload video to Bunny.net", default=False)

    transcript_output_path = prompt_path(
        "Transcript output path", default=output_dir / "transcript.vtt"
    )
    assert transcript_output_path is not None

    timestamps_output_path = prompt_path(
        "Timestamps output path", default=output_dir / "timestamps.json"
    )
    assert timestamps_output_path is not None
    timestamps_granularity = prompt_non_empty(
        "Timestamps granularity (low/medium/high)", default="medium"
    ).lower()
    if timestamps_granularity not in {"low", "medium", "high"}:
        print("Invalid granularity; defaulting to 'medium'.")
        timestamps_granularity = "medium"
    try:
        timestamp_notes = input(
            "Additional instructions for timestamps (optional): "
        ).strip()
    except EOFError:
        timestamp_notes = ""

    context_cards_output_path = output_dir / "context-cards.md"
    if include_context_cards:
        context_cards_output_path = prompt_path(
            "Context cards output path",
            default=context_cards_output_path,
        ) or context_cards_output_path

    linkedin_output_path = output_dir / "linkedin_post.md"
    if include_linkedin:
        linkedin_output_path = prompt_path(
            "LinkedIn post output path",
            default=linkedin_output_path,
        ) or linkedin_output_path

    twitter_output_path = output_dir / "twitter_post.md"
    if include_twitter:
        twitter_output_path = prompt_path(
            "Twitter post output path",
            default=twitter_output_path,
        ) or twitter_output_path

    bunny_library_id = os.getenv("BUNNY_LIBRARY_ID")
    bunny_access_key = os.getenv("BUNNY_ACCESS_KEY")
    bunny_collection_id = os.getenv("BUNNY_COLLECTION_ID")

    if upload_bunny:
        bunny_library_id = prompt_non_empty(
            "Bunny Library ID", default=bunny_library_id
        )
        bunny_access_key = prompt_non_empty(
            "Bunny Access Key", default=bunny_access_key
        )
        bunny_collection_id = input(
            "Bunny Collection ID (optional): "
        ).strip() or bunny_collection_id

    cli_bin = build_cli(args)

    return PipelineConfig(
        input_dir=input_dir,
        output_dir=output_dir,
        cli_bin=cli_bin,
        concat_title=concat_title,
        fast_concat=fast_concat,
        concat_output_path=custom_concat_path,
        timestamps_output_path=timestamps_output_path,
        timestamps_granularity=timestamps_granularity,
        timestamp_notes=timestamp_notes,
        transcript_output_path=transcript_output_path,
        include_context_cards=include_context_cards,
        context_cards_output_path=context_cards_output_path,
        include_linkedin=include_linkedin,
        linkedin_output_path=linkedin_output_path,
        include_seo=include_seo,
        include_twitter=include_twitter,
        twitter_output_path=twitter_output_path,
        upload_bunny=upload_bunny,
        bunny_library_id=bunny_library_id,
        bunny_access_key=bunny_access_key,
        bunny_collection_id=bunny_collection_id,
        metadata_path=output_dir / "metadata.json",
    )


def main(argv: list[str] | None = None) -> None:
    """Entry point for executing the full pipeline."""
    args = parse_args(argv if argv is not None else sys.argv[1:])

    config = gather_pipeline_config(args)

    require_env_vars(
        needs_bunny=config.upload_bunny,
        bunny_library_id=config.bunny_library_id,
        bunny_access_key=config.bunny_access_key,
    )

    config.output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nInput directory : {config.input_dir}")
    print(f"Output directory: {config.output_dir}")

    concat_command = [
        config.cli_bin,
        "concat",
        "--input-dir",
        str(config.input_dir),
        "--output-dir",
        str(config.output_dir),
        "--title",
        config.concat_title,
    ]
    if config.concat_output_path:
        concat_command.extend(["--output-path", str(config.concat_output_path)])
    if config.fast_concat:
        concat_command.append("--fast-concat")
        print("Fast concatenation enabled.")
    else:
        print("Fast concatenation disabled.")

    if config.upload_bunny:
        print("Bunny.net deployment enabled.")
    else:
        print("Bunny.net deployment disabled.")

    run_cli_step("Concatenating clips", concat_command)

    run_cli_step(
        "Generating timestamps",
        [
            config.cli_bin,
            "timestamps",
            "--input-dir",
            str(config.input_dir),
            "--output-dir",
            str(config.output_dir),
            "--output-path",
            str(config.timestamps_output_path),
            "--stamps-from-transcript",
            str(config.transcript_output_path),
            "--granularity",
            config.timestamps_granularity,
            "--timestamp-notes",
            config.timestamp_notes,
        ],
    )

    concatenated_video = (
        config.concat_output_path
        if config.concat_output_path
        else _resolve_concatenated_video(config.output_dir)
    )
    ensure_file(concatenated_video, "concatenated video")

    run_cli_step(
        "Generating transcript",
        [
            config.cli_bin,
            "transcript",
            "--video-path",
            str(concatenated_video),
            "--output-dir",
            str(config.output_dir),
            "--output-path",
            str(config.transcript_output_path),
        ],
    )

    ensure_file(config.transcript_output_path, "transcript file")

    if config.include_context_cards:
        run_cli_step(
            "Generating context cards",
            [
                config.cli_bin,
                "context-cards",
                "--input-transcript",
                str(config.transcript_output_path),
                "--output-dir",
                str(config.output_dir),
                "--output-path",
                str(config.context_cards_output_path),
            ],
        )

    if config.include_linkedin:
        run_cli_step(
            "Generating LinkedIn post",
            [
                config.cli_bin,
                "linkedin",
                "--transcript-path",
                str(config.transcript_output_path),
                "--output-dir",
                str(config.output_dir),
                "--output-path",
                str(config.linkedin_output_path),
            ],
        )

    if config.include_seo:
        run_cli_step(
            "Generating SEO keywords",
            [
                config.cli_bin,
                "seo",
                "--transcript-path",
                str(config.transcript_output_path),
                "--output-dir",
                str(config.output_dir),
            ],
        )

    if config.include_twitter:
        run_cli_step(
            "Generating Twitter post",
            [
                config.cli_bin,
                "twitter",
                "--transcript-path",
                str(config.transcript_output_path),
                "--output-dir",
                str(config.output_dir),
                "--output-path",
                str(config.twitter_output_path),
            ],
        )

    if config.upload_bunny:
        bunny_command = [
            config.cli_bin,
            "bunny-upload",
            "--video-path",
            str(concatenated_video),
            "--metadata-path",
            str(config.metadata_path),
            "--bunny-library-id",
            str(config.bunny_library_id),
            "--bunny-access-key",
            str(config.bunny_access_key),
        ]
        if config.bunny_collection_id:
            bunny_command.extend(["--bunny-collection-id", str(config.bunny_collection_id)])

        run_cli_step("Uploading video to Bunny.net", bunny_command)

    print("\nPipeline complete! Generated assets are located in:")
    print(f"  {config.output_dir}")


if __name__ == "__main__":
    main()
