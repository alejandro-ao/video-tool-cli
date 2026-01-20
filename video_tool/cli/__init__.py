"""Typer-based CLI for video-tool.

Command structure:
    video-tool pipeline ...              # root level (most common)
    video-tool video concat ...          # video group
    video-tool video description ...
    video-tool upload bunny-upload ...   # upload group
"""

from __future__ import annotations

import os
import sys
from typing import Optional

import typer
from dotenv import load_dotenv

from video_tool.logging_config import configure_logging
from video_tool.ui import console, step_error, step_complete, step_start
from video_tool.config import (
    load_config,
    set_llm_config,
    reset_config,
    get_llm_config,
    prompt_links_setup,
    CONFIG_PATH,
)

# Create main app and sub-apps
app = typer.Typer(
    name="video-tool",
    help="Video processing toolkit with AI-powered content generation",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

video_app = typer.Typer(
    name="video",
    help="Video processing and content generation commands",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

upload_app = typer.Typer(
    name="upload",
    help="Upload commands (bunny-upload, bunny-transcript, youtube-upload, etc.)",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

config_app = typer.Typer(
    name="config",
    help="Configuration commands (youtube-auth, llm settings, etc.)",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

# Register sub-apps
app.add_typer(video_app, name="video")
app.add_typer(upload_app, name="upload")
app.add_typer(config_app, name="config")

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


@config_app.command("llm")
def config_llm_command(
    show: bool = typer.Option(False, "--show", "-s", help="Show current config"),
    command: Optional[str] = typer.Option(None, "--command", "-c", help="Command to configure (e.g., description, seo)"),
    model: Optional[str] = typer.Option(None, "--model", "-m", help="Set model for command"),
    base_url: Optional[str] = typer.Option(None, "--base-url", "-b", help="Set base URL for command"),
    links: bool = typer.Option(False, "--links", "-l", help="Manage persistent links"),
    reset: bool = typer.Option(False, "--reset", help="Reset config to defaults"),
) -> None:
    """Configure LLM and links settings for video-tool."""
    import yaml

    if reset:
        reset_config()
        console.print(f"[green]Config reset to defaults[/green]")
        console.print(f"[dim]Config file: {CONFIG_PATH}[/dim]")
        return

    if links:
        prompt_links_setup()
        return

    if show:
        config = load_config()
        if command:
            llm_cfg = get_llm_config(command)
            console.print(f"[bold]{command}[/bold]:")
            console.print(f"  base_url: {llm_cfg.base_url}")
            console.print(f"  model: {llm_cfg.model}")
        else:
            console.print(yaml.safe_dump(config, default_flow_style=False, sort_keys=False))
        console.print(f"\n[dim]Config file: {CONFIG_PATH}[/dim]")
        return

    if model or base_url:
        set_llm_config(command, base_url=base_url, model=model)
        target = command or "default"
        step_complete(f"Config updated for '{target}'", str(CONFIG_PATH))
        return

    # No flags = show help
    console.print("Usage: video-tool config llm [OPTIONS]")
    console.print("\nOptions:")
    console.print("  --show, -s          Show current config")
    console.print("  --command, -c TEXT  Command to configure")
    console.print("  --model, -m TEXT    Set model")
    console.print("  --base-url, -b TEXT Set base URL")
    console.print("  --links, -l         Manage persistent links")
    console.print("  --reset             Reset to defaults")


@config_app.command("youtube-auth")
def config_youtube_auth(
    client_secrets: Optional[str] = typer.Option(
        None,
        "--client-secrets",
        "-c",
        help="Path to client_secrets.json from Google Cloud Console",
    ),
) -> None:
    """Authenticate with YouTube API using OAuth2.

    One-time setup: downloads refresh token after browser-based consent.
    Credentials saved to ~/.config/video-tool/youtube_credentials.json
    """
    from pathlib import Path
    from video_tool.video_processor.youtube import (
        YouTubeDeploymentMixin,
        CLIENT_SECRETS_PATH,
        CREDENTIALS_PATH,
    )

    # Prompt for client secrets if not provided
    if not client_secrets:
        if CLIENT_SECRETS_PATH.exists():
            console.print(f"[dim]Using existing client secrets: {CLIENT_SECRETS_PATH}[/dim]")
        else:
            from video_tool.ui import ask_path
            client_secrets = ask_path(
                "Path to client_secrets.json from Google Cloud Console",
                required=True,
            )

    step_start("YouTube OAuth2 Authentication", {
        "Client secrets": str(client_secrets or CLIENT_SECRETS_PATH),
        "Credentials will be saved to": str(CREDENTIALS_PATH),
    })

    console.print("\n[yellow]A browser window will open for Google OAuth consent.[/yellow]")
    console.print("[dim]Grant access to upload videos and manage captions.[/dim]\n")

    success = YouTubeDeploymentMixin.youtube_authenticate(client_secrets)

    if success:
        step_complete("YouTube authentication successful", str(CREDENTIALS_PATH))
    else:
        step_error("YouTube authentication failed")
        raise typer.Exit(1)


@config_app.command("youtube-status")
def config_youtube_status() -> None:
    """Check YouTube API credentials status."""
    from video_tool.video_processor.youtube import (
        YouTubeDeploymentMixin,
        CLIENT_SECRETS_PATH,
        CREDENTIALS_PATH,
    )

    status = YouTubeDeploymentMixin.get_youtube_credentials_status()

    console.print("\n[bold]YouTube Credentials Status[/bold]")
    console.print(f"  Client secrets: {'[green]Found[/green]' if status['client_secrets_exists'] else '[red]Missing[/red]'}")
    console.print(f"    Path: {CLIENT_SECRETS_PATH}")
    console.print(f"  Credentials: {'[green]Found[/green]' if status['credentials_exist'] else '[red]Missing[/red]'}")
    console.print(f"    Path: {CREDENTIALS_PATH}")

    if not status['credentials_exist']:
        console.print("\n[yellow]Run 'video-tool config youtube-auth' to authenticate.[/yellow]")


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
