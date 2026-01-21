"""Configuration management for video-tool LLM settings and credentials."""

from __future__ import annotations

import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

CONFIG_DIR = Path.home() / ".config" / "video-tool"
CONFIG_PATH = CONFIG_DIR / "config.yaml"
CREDENTIALS_PATH = CONFIG_DIR / "credentials.yaml"

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o"

# Maps credential key names to environment variable names
CREDENTIAL_KEYS = {
    "openai_api_key": "OPENAI_API_KEY",
    "groq_api_key": "GROQ_API_KEY",
    "bunny_library_id": "BUNNY_LIBRARY_ID",
    "bunny_access_key": "BUNNY_ACCESS_KEY",
    "bunny_collection_id": "BUNNY_COLLECTION_ID",
    "replicate_api_token": "REPLICATE_API_TOKEN",
}


@dataclass
class LLMConfig:
    """LLM configuration for a command."""

    base_url: str
    model: str


def config_exists() -> bool:
    """Check if config file exists."""
    return CONFIG_PATH.exists()


def is_llm_configured() -> bool:
    """Check if user has explicitly configured LLM settings.

    Returns True if config file exists with LLM settings, False otherwise.
    This distinguishes between 'user configured defaults' and 'never configured'.
    """
    if not CONFIG_PATH.exists():
        return False

    try:
        with open(CONFIG_PATH) as f:
            config = yaml.safe_load(f) or {}
        return "llm" in config and "default" in config.get("llm", {})
    except (OSError, yaml.YAMLError):
        return False


def load_config() -> dict:
    """Load config from file or return defaults."""
    if not CONFIG_PATH.exists():
        return {"llm": {"default": {"base_url": DEFAULT_BASE_URL, "model": DEFAULT_MODEL}}}

    try:
        with open(CONFIG_PATH) as f:
            config = yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        config = {}

    # Ensure llm.default exists
    if "llm" not in config:
        config["llm"] = {}
    if "default" not in config["llm"]:
        config["llm"]["default"] = {"base_url": DEFAULT_BASE_URL, "model": DEFAULT_MODEL}

    return config


def save_config(config: dict) -> None:
    """Persist config to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        yaml.safe_dump(config, f, default_flow_style=False, sort_keys=False)


def get_llm_config(command: str) -> LLMConfig:
    """Get base_url/model for a command (falls back to default)."""
    config = load_config()
    llm_config = config.get("llm", {})
    default = llm_config.get("default", {})
    command_config = llm_config.get(command, {})

    return LLMConfig(
        base_url=command_config.get("base_url", default.get("base_url", DEFAULT_BASE_URL)),
        model=command_config.get("model", default.get("model", DEFAULT_MODEL)),
    )


def set_llm_config(
    command: Optional[str] = None,
    *,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
) -> None:
    """Set LLM config for a command (or default if command is None)."""
    config = load_config()
    target = command or "default"

    if target not in config["llm"]:
        config["llm"][target] = {}

    if base_url is not None:
        config["llm"][target]["base_url"] = base_url
    if model is not None:
        config["llm"][target]["model"] = model

    save_config(config)


def reset_config() -> None:
    """Reset config to defaults."""
    config = {"llm": {"default": {"base_url": DEFAULT_BASE_URL, "model": DEFAULT_MODEL}}}
    save_config(config)


def get_links() -> list[dict]:
    """Get persistent links from config."""
    config = load_config()
    return config.get("links", [])


def set_links(links: list[dict]) -> None:
    """Save links list to config."""
    config = load_config()
    config["links"] = links
    save_config(config)


def prompt_links_setup() -> list[dict]:
    """Interactive add/edit links, saves result, returns links."""
    from video_tool.ui import ask_text, ask_confirm, console

    config = load_config()
    links = config.get("links", [])

    console.print("\n[bold]Persistent Links Configuration[/bold]")
    console.print("[dim]These links will be added to descriptions when --links is used[/dim]\n")

    if links:
        console.print("[bold]Current links:[/bold]")
        for i, link in enumerate(links, 1):
            console.print(f"  {i}. {link.get('description', '')}: {link.get('url', '')}")
        console.print()

        if ask_confirm("Clear existing links and start fresh?"):
            links = []

    if not links or ask_confirm("Add new links?"):
        console.print("[dim]Enter links (empty description to finish)[/dim]\n")
        while True:
            desc = ask_text("Link description (e.g., '🚀 My Bootcamp')", required=False)
            if not desc:
                break
            url = ask_text("URL", required=True)
            links.append({"description": desc, "url": url})
            console.print(f"  [green]Added:[/green] {desc}: {url}\n")

    set_links(links)
    console.print(f"\n[green]Links saved to config[/green]")
    return links


def ensure_config() -> dict:
    """Load config or run first-time setup if needed.

    Returns the config dict. If no config exists, prompts user for defaults.
    """
    if config_exists():
        return load_config()

    # First-time setup - prompt for defaults
    from video_tool.ui import ask_text, console

    console.print("\n[bold]First-time LLM configuration[/bold]")
    console.print(f"[dim]Config will be saved to: {CONFIG_PATH}[/dim]\n")

    base_url = ask_text(
        f"Base URL for OpenAI-compatible API (default: {DEFAULT_BASE_URL})",
        required=False,
    )
    if not base_url:
        base_url = DEFAULT_BASE_URL

    model = ask_text(f"Default model (default: {DEFAULT_MODEL})", required=False)
    if not model:
        model = DEFAULT_MODEL

    config = {"llm": {"default": {"base_url": base_url, "model": model}}}
    save_config(config)

    console.print(f"\n[green]Config saved to {CONFIG_PATH}[/green]\n")
    return config


def prompt_optional_llm_setup() -> bool:
    """Prompt user to configure LLM for optional features. Returns True if configured.

    Used for features like timestamp title refinement that enhance output but aren't required.
    If user skips configuration, the feature will be skipped.
    """
    from video_tool.ui import ask_text, ask_confirm, console

    console.print("\n[bold]LLM Configuration (Optional)[/bold]")
    console.print("[dim]An LLM can improve chapter titles using transcript context.[/dim]")
    console.print("[dim]Leave empty to skip this enhancement.[/dim]\n")

    if not ask_confirm("Configure LLM for title refinement?", default=False):
        console.print("[dim]Skipping LLM configuration - using default titles[/dim]\n")
        return False

    base_url = ask_text(
        f"Base URL for OpenAI-compatible API (default: {DEFAULT_BASE_URL})",
        required=False,
    )
    model = ask_text(f"Model name (default: {DEFAULT_MODEL})", required=False)

    # If both empty, user wants to skip
    if not base_url and not model:
        console.print("[dim]No LLM configured - using default titles[/dim]\n")
        return False

    # Save config with provided or default values
    config = {
        "llm": {
            "default": {
                "base_url": base_url or DEFAULT_BASE_URL,
                "model": model or DEFAULT_MODEL,
            }
        }
    }
    save_config(config)
    console.print(f"\n[green]LLM config saved to {CONFIG_PATH}[/green]\n")
    return True


# --- Credential Management ---


def load_credentials() -> dict:
    """Load credentials from yaml file."""
    if not CREDENTIALS_PATH.exists():
        return {}
    try:
        with open(CREDENTIALS_PATH) as f:
            return yaml.safe_load(f) or {}
    except (OSError, yaml.YAMLError):
        return {}


def save_credentials(creds: dict) -> None:
    """Save credentials with secure permissions (0600)."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CREDENTIALS_PATH, "w") as f:
        yaml.safe_dump(creds, f, default_flow_style=False, sort_keys=False)
    os.chmod(CREDENTIALS_PATH, stat.S_IRUSR | stat.S_IWUSR)


def _is_valid_credential(value: Optional[str]) -> bool:
    """Check if a credential value looks valid (not empty, not placeholder)."""
    if not value:
        return False
    value = value.strip()
    # Reject empty, ellipsis literals, or placeholder-looking values
    invalid_values = {"", "...", "Ellipsis", "None", "null", "undefined"}
    if value in invalid_values:
        return False
    # Must be at least a few characters
    if len(value) < 4:
        return False
    return True


def get_credential(key: str) -> Optional[str]:
    """Get credential from credentials file.

    Args:
        key: Credential key name (e.g., "openai_api_key")

    Returns:
        The credential value or None if not found/invalid
    """
    creds = load_credentials()
    val = creds.get(key)
    if _is_valid_credential(val):
        return val
    return None


def prompt_and_save_credential(
    key: str,
    label: str,
    required: bool = True,
    hide_input: bool = True,
) -> Optional[str]:
    """Prompt user for credential and save it.

    Args:
        key: Credential key name (e.g., "openai_api_key")
        label: Human-readable label for the prompt
        required: Whether the credential is required
        hide_input: Whether to hide input (for API keys)

    Returns:
        The credential value or None if skipped
    """
    import typer

    prompt_text = f"{label}"
    if not required:
        prompt_text += " (optional, press Enter to skip)"

    while True:
        try:
            value = typer.prompt(prompt_text, default="", hide_input=hide_input)
        except typer.Abort:
            return None

        value = value.strip() if value else ""

        # Empty input
        if not value:
            if required:
                typer.echo("This field is required. Please enter a value.")
                continue
            return None

        # Validate it looks like a real credential
        if not _is_valid_credential(value):
            typer.echo("Invalid value. Please enter a valid API key.")
            continue

        break

    # Save to credentials file
    creds = load_credentials()
    creds[key] = value
    save_credentials(creds)

    return value


def clear_credentials() -> None:
    """Remove all stored credentials."""
    if CREDENTIALS_PATH.exists():
        CREDENTIALS_PATH.unlink()


def mask_credential(value: str) -> str:
    """Mask a credential for display (show first 4 and last 4 chars)."""
    if not value or len(value) < 12:
        return "***"
    return f"{value[:4]}...{value[-4:]}"
