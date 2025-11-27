"""Orchestrate the full video-tool workflow for a directory of clips.

Usage:
    python scripts/run_full_pipeline.py

The script will prompt you for the input directory containing your video clips.
It mirrors the prior shell helper while providing better portability
and error handling. It expects the video-tool CLI to be installed and
discoverable on PATH (override via the --cli-bin flag or VIDEO_TOOL_CLI env).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path
from dotenv import load_dotenv

load_dotenv('../.env')

REQUIRED_ENV_VARS = (
    "OPENAI_API_KEY",
    "GROQ_API_KEY",
    "BUNNY_LIBRARY_ID",
    "BUNNY_ACCESS_KEY",
)


def require_env_vars() -> None:
    """Ensure all required environment variables are present."""
    missing = [name for name in REQUIRED_ENV_VARS if not os.getenv(name)]
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
        answer = answer.replace('\\ ', ' ')
            
        input_dir = Path(answer).expanduser().resolve()
        if not input_dir.exists():
            print(f"Directory '{input_dir}' does not exist. Please try again.")
            print("Tip: You can use quotes around the path or escape spaces with backslashes.")
            continue
        
        if not input_dir.is_dir():
            print(f"'{input_dir}' is not a directory. Please try again.")
            continue
            
        return input_dir


def prompt_fast_concat() -> bool:
    """Ask the user whether to enable fast concatenation."""
    try:
        answer = input("Use fast concatenation? [y/N]: ").strip()
    except EOFError:
        return False
    return answer.lower().startswith("y")


def prompt_bunny_deployment() -> bool:
    """Ask the user whether to deploy the video to Bunny.net."""
    try:
        answer = input("Deploy video to Bunny.net? [y/N]: ").strip()
    except EOFError:
        return False
    return answer.lower().startswith("y")


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


def main(argv: list[str] | None = None) -> None:
    
    args = parse_args(argv or sys.argv[1:])

    input_dir = prompt_input_directory()

    require_env_vars()
    cli_bin = build_cli(args)

    output_dir = input_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"Input directory : {input_dir}")
    print(f"Output directory: {output_dir}")

    fast_concat = prompt_fast_concat()
    deploy_to_bunny = prompt_bunny_deployment()

    concat_command = [cli_bin, "concat", "--input-dir", str(input_dir)]
    if fast_concat:
        concat_command.append("--fast-concat")
        print("Fast concatenation enabled.")
    else:
        print("Fast concatenation disabled.")
    
    if deploy_to_bunny:
        print("Bunny.net deployment enabled.")
    else:
        print("Bunny.net deployment disabled.")

    run_cli_step("Concatenating clips", concat_command)

    run_cli_step(
        "Generating timestamps",
        [cli_bin, "timestamps", "--input-dir", str(input_dir)],
    )

    concatenated_video = output_dir / "concatenated.mp4"
    ensure_file(concatenated_video, "concatenated video")

    transcript_path = output_dir / "transcript.vtt"
    run_cli_step(
        "Generating transcript",
        [
            cli_bin,
            "transcript",
            "--video-path",
            str(concatenated_video),
            "--output-path",
            str(transcript_path),
        ],
    )

    ensure_file(transcript_path, "transcript file")

    run_cli_step(
        "Generating context cards",
        [
            cli_bin,
            "context-cards",
            "--input-transcript",
            str(transcript_path),
            "--output-path",
            str(output_dir / "context-cards.md"),
        ],
    )

    run_cli_step(
        "Generating LinkedIn post",
        [
            cli_bin,
            "linkedin",
            "--transcript-path",
            str(transcript_path),
            "--output-path",
            str(output_dir / "linkedin_post.md"),
        ],
    )

    run_cli_step(
        "Generating SEO keywords",
        [cli_bin, "seo", "--transcript-path", str(transcript_path)],
    )

    run_cli_step(
        "Generating Twitter post",
        [
            cli_bin,
            "twitter",
            "--transcript-path",
            str(transcript_path),
            "--output-path",
            str(output_dir / "twitter_post.md"),
        ],
    )

    if deploy_to_bunny:
        bunny_command = [
            cli_bin,
            "bunny-upload",
            "--video-path",
            str(concatenated_video),
            "--bunny-library-id",
            os.environ["BUNNY_LIBRARY_ID"],
            "--bunny-access-key",
            os.environ["BUNNY_ACCESS_KEY"],
        ]
        bunny_collection = os.getenv("BUNNY_COLLECTION_ID")
        if bunny_collection:
            bunny_command.extend(["--bunny-collection-id", bunny_collection])

        run_cli_step("Uploading video to Bunny.net", bunny_command)

    print("\nPipeline complete! Generated assets are located in:")
    print(f"  {output_dir}")


if __name__ == "__main__":
    main()
