"""Shared CLI path resolution helpers.

Eliminates the repeated pattern of resolving output paths across all CLI commands.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from video_tool.ui import normalize_path


def resolve_output_path(
    output_path: Optional[Path],
    input_path: Path,
    default_name: str,
    suffix: Optional[str] = None,
    prompt: bool = False,
    prompt_text: Optional[str] = None,
) -> Path:
    """Resolve an output path from CLI flags, falling back to defaults.

    This replaces the ~15 near-identical output-path resolution blocks
    scattered across the CLI commands.

    Args:
        output_path: Explicit --output path from the user (may be None).
        input_path: The input file/directory used to resolve relative paths.
        default_name: Default filename when the user doesn't supply one.
        suffix: Force the output to have this suffix (e.g. '.mp4', '.vtt').
            If None, the suffix from output_path or default_name is kept.
        prompt: If True and output_path is None, prompt interactively.
        prompt_text: Override prompt text.
    Returns:
        An absolute Path ready for use.
    """
    if output_path is not None:
        resolved = Path(normalize_path(str(output_path)))
        if not resolved.is_absolute():
            resolved = input_path / resolved
    elif prompt:
        from video_tool.ui import ask_path

        prompt_msg = prompt_text or f"Output path (defaults to {default_name})"
        output_path_str = ask_path(prompt_msg, required=False)
        if output_path_str:
            resolved = Path(output_path_str)
            if not resolved.is_absolute():
                resolved = input_path / resolved
        else:
            resolved = input_path / default_name
    else:
        resolved = input_path / default_name

    if suffix and resolved.suffix.lower() != suffix:
        resolved = resolved.with_suffix(suffix)

    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved