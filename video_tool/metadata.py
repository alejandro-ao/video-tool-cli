"""Shared metadata.json read/write helpers for CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

from video_tool.ui import console, step_warning


def read_metadata(path: Path) -> dict | None:
    """Read metadata.json if it exists.

    Returns the parsed dict, or None if the file is missing or invalid.
    """
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def write_metadata(path: Path, data: dict) -> None:
    """Write metadata.json, creating parent directories as needed.

    Prints a dim status line on success, or a warning on failure.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        console.print(f"  [dim]Metadata:[/dim] {path}")
    except OSError as exc:
        step_warning(f"Unable to write metadata: {exc}")
