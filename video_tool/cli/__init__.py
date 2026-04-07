"""Typer-based CLI for video-tool.

Command structure:
    video-tool pipeline ...                # root level (most common)
    video-tool video concat ...            # video group (FFmpeg operations)
    video-tool generate description ...    # generate group (AI content)
    video-tool upload bunny-upload ...     # upload group
"""

from __future__ import annotations

import os
import sys
from typing import List, Optional

import typer
from dotenv import load_dotenv

from video_tool.logging_config import configure_logging
from video_tool.ui import console, step_error, step_complete, step_start, step_info
from video_tool.config import (
    load_config,
    set_llm_config,
    reset_config,
    get_llm_config,
    prompt_links_setup,
    CONFIG_PATH,
    CREDENTIALS_PATH,
    CREDENTIAL_KEYS,
    get_credential,
    load_credentials,
    save_credentials,
    clear_credentials,
    mask_credential,
    prompt_and_save_credential,
    set_credential,
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
    help="Video processing commands (FFmpeg operations)",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

generate_app = typer.Typer(
    name="generate",
    help="AI-powered content generation (transcripts, descriptions, context cards)",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

upload_app = typer.Typer(
    name="upload",
    help="Upload commands (bunny-video, bunny-transcript, youtube-video, etc.)",
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
app.add_typer(generate_app, name="generate")
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


def _is_interactive() -> bool:
    """Check if running in an interactive terminal."""
    return sys.stdin.isatty()


def ensure_openai_key() -> bool:
    """Ensure OpenAI key exists, prompting interactively if possible."""
    if get_credential("openai_api_key"):
        return True
    # Clear, structured error for both humans and AI assistants
    console.print("\n[bold red]═══ AUTHENTICATION REQUIRED ═══[/bold red]")
    console.print("[red]Error: OpenAI API key not configured[/red]")
    console.print("\n[bold yellow]To fix this, run:[/bold yellow]")
    console.print("[bold cyan]  video-tool config keys[/bold cyan]")
    console.print("\n[dim]This command will prompt you for your OpenAI API key.[/dim]")
    console.print("[dim]Get your key at: https://platform.openai.com/api-keys[/dim]\n")
    if not _is_interactive():
        return False
    return prompt_and_save_credential("openai_api_key", "OpenAI API Key") is not None


def ensure_groq_key() -> bool:
    """Ensure Groq key exists, prompting interactively if possible."""
    if get_credential("groq_api_key"):
        return True
    # Clear, structured error for both humans and AI assistants
    console.print("\n[bold red]═══ AUTHENTICATION REQUIRED ═══[/bold red]")
    console.print("[red]Error: Groq API key not configured[/red]")
    console.print("\n[bold yellow]To fix this, run:[/bold yellow]")
    console.print("[bold cyan]  video-tool config keys[/bold cyan]")
    console.print("\n[dim]This command will prompt you for your Groq API key.[/dim]")
    console.print("[dim]Get your key at: https://console.groq.com/keys[/dim]\n")
    if not _is_interactive():
        return False
    return prompt_and_save_credential("groq_api_key", "Groq API Key") is not None


def validate_ai_env_vars() -> bool:
    """Ensure required AI API keys exist, prompting if needed."""
    if not ensure_openai_key():
        return False
    if not ensure_groq_key():
        return False
    return True


def validate_bunny_env_vars(
    library_id: Optional[str] = None,
    access_key: Optional[str] = None,
) -> bool:
    """Check that Bunny.net credentials are available (no prompting)."""
    missing = []
    if not (library_id or get_credential("bunny_library_id")):
        missing.append("BUNNY_LIBRARY_ID")
    if not (access_key or get_credential("bunny_access_key")):
        missing.append("BUNNY_ACCESS_KEY")

    if missing:
        console.print("\n[bold red]═══ AUTHENTICATION REQUIRED ═══[/bold red]")
        console.print(f"[red]Error: Missing Bunny credentials: {', '.join(missing)}[/red]")
        console.print("\n[bold yellow]To fix this, run:[/bold yellow]")
        console.print("[bold cyan]  video-tool config keys[/bold cyan]")
        console.print("\n[dim]This command will prompt you for your Bunny.net credentials.[/dim]\n")
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


@config_app.command("keys")
def config_keys_command(
    show: bool = typer.Option(False, "--show", "-s", help="Show current API keys (masked)"),
    reset: bool = typer.Option(False, "--reset", help="Clear all stored credentials"),
    set_creds: Optional[List[str]] = typer.Option(
        None, "--set", help="Set credential non-interactively (KEY=VALUE)"
    ),
) -> None:
    """Manage API keys for video-tool services.

    Keys are stored in ~/.config/video-tool/credentials.yaml with secure permissions.

    Use --set for non-interactive setup:
        video-tool config keys --set groq_api_key=gsk_xxx
        video-tool config keys --set groq_api_key=xxx --set openai_api_key=yyy
    """
    if reset:
        clear_credentials()
        step_complete("Credentials cleared", str(CREDENTIALS_PATH))
        return

    # Handle non-interactive --set
    if set_creds:
        for item in set_creds:
            if "=" not in item:
                step_error("Invalid format", f"Expected KEY=VALUE, got: {item}")
                raise typer.Exit(1)
            key, value = item.split("=", 1)
            if key not in CREDENTIAL_KEYS:
                valid_keys = ", ".join(CREDENTIAL_KEYS.keys())
                step_error("Invalid key", f"'{key}' not in: {valid_keys}")
                raise typer.Exit(1)
            if not set_credential(key, value):
                step_error("Invalid value", f"Value for '{key}' is invalid")
                raise typer.Exit(1)
            step_complete("Set", f"{key}")
        return

    if show:
        console.print("\n[bold]API Keys[/bold]")
        console.print(f"[dim]Credentials file: {CREDENTIALS_PATH}[/dim]\n")

        for key in CREDENTIAL_KEYS:
            label = key.replace("_", " ").title()
            value = get_credential(key)

            if value:
                console.print(f"  {label}: [green]{mask_credential(value)}[/green]")
            else:
                console.print(f"  {label}: [red]Not set[/red]")
        return

    # Interactive setup
    console.print("\n[bold]API Keys Configuration[/bold]")
    console.print(f"[dim]Credentials will be saved to: {CREDENTIALS_PATH}[/dim]")
    console.print("[dim]Press Enter to skip optional keys, Ctrl+C to cancel[/dim]\n")

    # Required keys
    console.print("[bold]Required:[/bold]")

    if not get_credential("openai_api_key"):
        console.print("[dim]https://platform.openai.com/api-keys[/dim]")
        prompt_and_save_credential("openai_api_key", "OpenAI API Key", required=True)
    else:
        console.print(f"  OpenAI API Key: [green]Already set[/green]")

    if not get_credential("groq_api_key"):
        console.print("[dim]https://console.groq.com/keys[/dim]")
        prompt_and_save_credential("groq_api_key", "Groq API Key", required=True)
    else:
        console.print(f"  Groq API Key: [green]Already set[/green]")

    # Optional keys
    console.print("\n[bold]Optional:[/bold]")

    if not get_credential("bunny_library_id"):
        prompt_and_save_credential("bunny_library_id", "Bunny Library ID", required=False, hide_input=False)
    else:
        console.print(f"  Bunny Library ID: [green]Already set[/green]")

    if not get_credential("bunny_access_key"):
        prompt_and_save_credential("bunny_access_key", "Bunny Access Key", required=False)
    else:
        console.print(f"  Bunny Access Key: [green]Already set[/green]")

    if not get_credential("replicate_api_token"):
        console.print("[dim]https://replicate.com/account/api-tokens[/dim]")
        prompt_and_save_credential("replicate_api_token", "Replicate API Token", required=False)
    else:
        console.print(f"  Replicate API Token: [green]Already set[/green]")

    # X OAuth - point to x-auth command
    x_creds = ["x_api_key", "x_api_secret", "x_access_token", "x_access_token_secret"]
    x_configured = all(get_credential(k) for k in x_creds)
    if x_configured:
        console.print("  X (Twitter) OAuth: [green]Already configured[/green]")
    else:
        console.print("  X (Twitter) OAuth: [yellow]Not configured[/yellow]")
        console.print("[dim]  Run 'video-tool config x-auth' to set up X authentication[/dim]")

    if not get_credential("linkedin_access_token"):
        console.print("[dim]https://www.linkedin.com/developers/apps[/dim]")
        prompt_and_save_credential("linkedin_access_token", "LinkedIn Access Token", required=False)
    else:
        console.print(f"  LinkedIn Access Token: [green]Already set[/green]")

    if not get_credential("linkedin_author_urn"):
        prompt_and_save_credential(
            "linkedin_author_urn",
            "LinkedIn Author URN (e.g., urn:li:person:...)",
            required=False,
            hide_input=False,
        )
    else:
        console.print(f"  LinkedIn Author URN: [green]Already set[/green]")

    step_complete("Credentials saved", str(CREDENTIALS_PATH))


@config_app.command("youtube-auth")
def config_youtube_auth(
    client_secrets: Optional[str] = typer.Option(
        None,
        "--client-secrets",
        "-c",
        help="Path to client_secrets.json from Google Cloud Console",
    ),
    profile: str = typer.Option(
        "default",
        "--profile",
        "-p",
        help="Named YouTube auth profile to save",
    ),
    activate: bool = typer.Option(
        True,
        "--activate/--no-activate",
        help="Make this profile the default active profile after auth",
    ),
) -> None:
    """Authenticate with YouTube API using OAuth2.

    One-time setup: downloads refresh token after browser-based consent.
    Credentials are saved under ~/.config/video-tool/youtube/<profile>.json
    """
    from pathlib import Path
    from video_tool.video_processor.youtube import (
        YouTubeDeploymentMixin,
        CLIENT_SECRETS_PATH,
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
        "Profile": profile,
        "Activate profile": "yes" if activate else "no",
        "Credentials will be saved to": str(YouTubeDeploymentMixin.get_youtube_credentials_path(profile)),
    })

    console.print("\n[yellow]A browser window will open for Google OAuth consent.[/yellow]")
    console.print("[dim]Grant access to upload videos and manage captions.[/dim]\n")

    success = YouTubeDeploymentMixin.youtube_authenticate(
        client_secrets,
        profile=profile,
        set_active=activate,
    )

    if success:
        step_complete(
            "YouTube authentication successful",
            str(YouTubeDeploymentMixin.get_youtube_credentials_path(profile)),
        )
    else:
        step_error("YouTube authentication failed")
        raise typer.Exit(1)


@config_app.command("youtube-status")
def config_youtube_status(
    profile: Optional[str] = typer.Option(
        None,
        "--profile",
        "-p",
        help="Inspect a specific YouTube auth profile",
    ),
) -> None:
    """Check YouTube API credentials status."""
    from video_tool.video_processor.youtube import (
        YouTubeDeploymentMixin,
        CLIENT_SECRETS_PATH,
    )

    status = YouTubeDeploymentMixin.get_youtube_credentials_status()

    console.print("\n[bold]YouTube Credentials Status[/bold]")
    console.print(f"  Client secrets: {'[green]Found[/green]' if status['client_secrets_exists'] else '[red]Missing[/red]'}")
    console.print(f"    Path: {CLIENT_SECRETS_PATH}")
    console.print(f"  Credentials: {'[green]Found[/green]' if status['credentials_exist'] else '[red]Missing[/red]'}")
    console.print(f"  Active profile: {status['active_profile']}")

    profiles = status.get("profiles", [])
    if profiles:
        console.print("\n  Saved profiles:")
        matched_profile = False
        for item in profiles:
            if profile and item.get("name") != profile:
                continue
            matched_profile = True
            suffix = " [green](active)[/green]" if item.get("is_active") == "true" else ""
            channel = item.get("channel_title") or "Unknown channel"
            channel_id = item.get("channel_id") or "unknown"
            console.print(f"    - {item['name']}{suffix}")
            console.print(f"      Channel: {channel} ({channel_id})")
            console.print(f"      Path: {item['path']}")
        if profile and not matched_profile:
            console.print(f"\n  Profile '{profile}' not found.")
    elif profile:
        console.print(f"\n  Profile '{profile}' not found.")

    if not status['credentials_exist']:
        console.print("\n[yellow]Run 'video-tool config youtube-auth' to authenticate.[/yellow]")


@config_app.command("youtube-use")
def config_youtube_use(
    profile: str = typer.Argument(..., help="Saved YouTube auth profile to activate"),
) -> None:
    """Set the active YouTube auth profile used by upload commands."""
    from video_tool.video_processor.youtube import YouTubeDeploymentMixin

    credentials_path = YouTubeDeploymentMixin.get_youtube_credentials_path(profile)
    if not credentials_path.exists():
        step_error(f"YouTube profile not found: {profile}")
        raise typer.Exit(1)

    active_path = YouTubeDeploymentMixin.set_active_youtube_profile(profile)
    step_complete("Active YouTube profile updated", str(active_path))


@config_app.command("x-auth")
def config_x_auth() -> None:
    """Authenticate with X (Twitter) API using OAuth 1.0a.

    This sets up the 4 credentials needed for X API access:
    - API Key (Consumer Key)
    - API Secret (Consumer Secret)
    - Access Token
    - Access Token Secret

    Get these from https://developer.x.com/en/portal/dashboard
    """
    import webbrowser
    from requests_oauthlib import OAuth1Session

    console.print("\n[bold]X (Twitter) OAuth Setup[/bold]")
    console.print("[dim]You'll need a Twitter Developer account and an app with OAuth 1.0a enabled.[/dim]")
    console.print("[dim]Get credentials at: https://developer.x.com/en/portal/dashboard[/dim]\n")

    # Get API key and secret
    api_key = get_credential("x_api_key")
    if api_key:
        console.print(f"  API Key: [green]Already set ({mask_credential(api_key)})[/green]")
        from video_tool.ui import ask_confirm
        if not ask_confirm("Re-enter API credentials?", default=False):
            # Check if all creds exist
            if all(get_credential(k) for k in ["x_api_key", "x_api_secret", "x_access_token", "x_access_token_secret"]):
                step_complete("X OAuth credentials already configured")
                return
    else:
        console.print("[dim]Enter your app's API Key and Secret from the Developer Portal.[/dim]")

    api_key = prompt_and_save_credential("x_api_key", "API Key (Consumer Key)", required=True, hide_input=False)
    if not api_key:
        step_error("API Key is required")
        raise typer.Exit(1)

    api_secret = prompt_and_save_credential("x_api_secret", "API Secret (Consumer Secret)", required=True)
    if not api_secret:
        step_error("API Secret is required")
        raise typer.Exit(1)

    # Check if user already has access tokens
    console.print("\n[bold]Access Tokens[/bold]")
    console.print("[dim]You can get these from the Developer Portal (Keys and tokens > Access Token and Secret)[/dim]")
    console.print("[dim]Or use the OAuth flow to generate new ones.[/dim]\n")

    from video_tool.ui import ask_confirm
    if ask_confirm("Do you have Access Token and Secret already?", default=True):
        access_token = prompt_and_save_credential("x_access_token", "Access Token", required=True, hide_input=False)
        if not access_token:
            step_error("Access Token is required")
            raise typer.Exit(1)

        access_token_secret = prompt_and_save_credential("x_access_token_secret", "Access Token Secret", required=True)
        if not access_token_secret:
            step_error("Access Token Secret is required")
            raise typer.Exit(1)

        step_complete("X OAuth credentials saved", str(CREDENTIALS_PATH))
        return

    # OAuth flow
    console.print("\n[yellow]Starting OAuth authorization flow...[/yellow]")

    request_token_url = "https://api.twitter.com/oauth/request_token"
    authorization_url = "https://api.twitter.com/oauth/authorize"
    access_token_url = "https://api.twitter.com/oauth/access_token"

    try:
        oauth = OAuth1Session(api_key, client_secret=api_secret, callback_uri="oob")
        fetch_response = oauth.fetch_request_token(request_token_url)
        resource_owner_key = fetch_response.get("oauth_token")
        resource_owner_secret = fetch_response.get("oauth_token_secret")

        auth_url = oauth.authorization_url(authorization_url)
        console.print(f"\n[bold]Open this URL to authorize:[/bold]\n{auth_url}\n")

        webbrowser.open(auth_url)

        verifier = typer.prompt("Enter the PIN from Twitter")

        oauth = OAuth1Session(
            api_key,
            client_secret=api_secret,
            resource_owner_key=resource_owner_key,
            resource_owner_secret=resource_owner_secret,
            verifier=verifier,
        )
        oauth_tokens = oauth.fetch_access_token(access_token_url)

        # Save the tokens
        creds = load_credentials()
        creds["x_access_token"] = oauth_tokens["oauth_token"]
        creds["x_access_token_secret"] = oauth_tokens["oauth_token_secret"]
        save_credentials(creds)

        step_complete("X OAuth credentials saved", str(CREDENTIALS_PATH))

    except Exception as e:
        step_error(f"OAuth flow failed: {e}")
        console.print("[dim]Try entering Access Token and Secret manually instead.[/dim]")
        raise typer.Exit(1)


# Import command modules to register commands
from video_tool.cli import video_commands  # noqa: E402, F401
from video_tool.cli import generate_commands  # noqa: E402, F401
from video_tool.cli import deploy_commands  # noqa: E402, F401
from video_tool.cli import pipeline  # noqa: E402, F401
from video_tool.cli import social_commands  # noqa: E402, F401


def main() -> None:
    """Entry point for the CLI."""
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[bold yellow]Interrupted by user.[/bold yellow]")
        sys.exit(130)


if __name__ == "__main__":
    main()
