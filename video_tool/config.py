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
