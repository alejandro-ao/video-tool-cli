"""Shared constants for supported video formats."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

# Containers we handle throughout the pipeline. Keep lowercase with leading dots.
SUPPORTED_VIDEO_SUFFIXES: tuple[str, ...] = (".mp4", ".mov")
SUPPORTED_VIDEO_SUFFIX_SET = frozenset(suffix.lower() for suffix in SUPPORTED_VIDEO_SUFFIXES)

# Audio formats accepted for direct transcription (skips extraction).
SUPPORTED_AUDIO_SUFFIXES: tuple[str, ...] = (".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg")
SUPPORTED_AUDIO_SUFFIX_SET = frozenset(suffix.lower() for suffix in SUPPORTED_AUDIO_SUFFIXES)


def is_supported_video_file(candidate: Path | str, *, suffixes: Iterable[str] | None = None) -> bool:
    """
    Return True when the given path string or Path has a supported video suffix.

    Parameters
    ----------
    candidate:
        Filesystem path or filename to inspect.
    suffixes:
        Optional override of allowed suffixes; defaults to SUPPORTED_VIDEO_SUFFIXES.
    """
    suffix_set = (
        frozenset(suffix.lower() for suffix in suffixes)
        if suffixes is not None
        else SUPPORTED_VIDEO_SUFFIX_SET
    )
    suffix = candidate.suffix if isinstance(candidate, Path) else Path(candidate).suffix
    return suffix.lower() in suffix_set
