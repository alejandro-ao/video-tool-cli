"""Typer-based CLI for video-tool.

Command structure:
    video-tool pipeline ...              # root level (most common)
    video-tool video concat ...          # video group
    video-tool video timestamps ...
    video-tool content seo ...           # content group
    video-tool content linkedin ...
    video-tool deploy bunny-upload ...   # deploy group
"""

from __future__ import annotations

import os
import sys
from typing import Optional

import typer
from dotenv import load_dotenv

from video_tool.logging_config import configure_logging
from video_tool.ui import console, step_error

# Create main app and sub-apps
app = typer.Typer(
    name="video-tool",
    help="Video processing toolkit with AI-powered content generation",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

video_app = typer.Typer(
    name="video",
    help="Video processing commands (concat, timestamps, transcript, etc.)",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

content_app = typer.Typer(
    name="content",
    help="Content generation commands (description, seo, linkedin, etc.)",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

deploy_app = typer.Typer(
    name="deploy",
    help="Deployment commands (bunny-upload, bunny-transcript, etc.)",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

# Register sub-apps
app.add_typer(video_app, name="video")
app.add_typer(content_app, name="content")
app.add_typer(deploy_app, name="deploy")

# Global state for verbose flag
_verbose = False


def get_verbose() -> bool:
    """Get the global verbose flag."""
    return _verbose


@app.callback()
def main_callback(
    verbose: bool = typer.Option(
        False,
        "--verbose",
        "-v",
        help="Enable verbose output (show INFO logs in terminal)",
    ),
) -> None:
    """Video processing toolkit with AI-powered content generation."""
    global _verbose
    _verbose = verbose

    # Load environment variables
    load_dotenv()

    # Configure logging based on verbose flag
    configure_logging(verbose=verbose)


def validate_ai_env_vars() -> bool:
    """Check that required AI API keys are set."""
    missing = [var for var in ("OPENAI_API_KEY", "GROQ_API_KEY") if not os.getenv(var)]
    if missing:
        step_error(f"Missing required environment variables: {', '.join(missing)}")
        return False
    return True


def validate_bunny_env_vars(
    library_id: Optional[str] = None,
    access_key: Optional[str] = None,
) -> bool:
    """Check that Bunny.net credentials are available."""
    missing = []
    if not (library_id or os.getenv("BUNNY_LIBRARY_ID")):
        missing.append("BUNNY_LIBRARY_ID")
    if not (access_key or os.getenv("BUNNY_ACCESS_KEY")):
        missing.append("BUNNY_ACCESS_KEY")

    if missing:
        step_error(f"Missing Bunny credentials: {', '.join(missing)}")
        return False
    return True


# Import command modules to register commands
from video_tool.cli import video_commands  # noqa: E402, F401
from video_tool.cli import content_commands  # noqa: E402, F401
from video_tool.cli import deploy_commands  # noqa: E402, F401
from video_tool.cli import pipeline  # noqa: E402, F401


def main() -> None:
    """Entry point for the CLI."""
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Interrupted by user.[/bold yellow]")
        sys.exit(130)


if __name__ == "__main__":
    main()
