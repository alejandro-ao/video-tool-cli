"""Configuration management for video-tool LLM settings."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import yaml

CONFIG_DIR = Path.home() / ".config" / "video-tool"
CONFIG_PATH = CONFIG_DIR / "config.yaml"

DEFAULT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_MODEL = "gpt-4o"


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
