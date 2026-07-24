"""System-aware transcription model recommendations."""

from __future__ import annotations

import importlib.util
import platform
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class Recommendation:
    """A model recommendation and human-readable rationale."""

    model_id: str
    reasons: tuple[str, ...]


def recommend_model(*, language: str | None = None, available_only: bool = False) -> Recommendation:
    """Recommend a model based on platform, architecture, language, and installed runtimes."""
    multilingual = language not in (None, "auto", "en", "english")
    machine = platform.machine().lower()
    if sys.platform == "darwin" and machine in {"arm64", "aarch64"}:
        if multilingual:
            candidate = "mlx/whisper-large-v3-turbo"
            module = "mlx_whisper"
            reason = "multilingual transcription requested"
        else:
            candidate = "mlx/parakeet-tdt-0.6b-v2"
            module = "parakeet_mlx"
            reason = "Parakeet is fast and accurate for English"
        if not available_only or importlib.util.find_spec(module):
            return Recommendation(
                candidate, ("Apple Silicon detected", reason, "MLX uses unified-memory GPU acceleration")
            )
    if _has_cuda() and (not multilingual):
        if not available_only or importlib.util.find_spec("nemo"):
            return Recommendation(
                "nemo/parakeet-tdt-0.6b-v2", ("NVIDIA CUDA detected", "Parakeet is optimized for English")
            )
    if not available_only or importlib.util.find_spec("faster_whisper"):
        return Recommendation(
            "faster-whisper/large-v3-turbo",
            ("Portable local runtime selected", "faster-whisper supports CPU and CUDA"),
        )
    return Recommendation(
        "groq/whisper-large-v3-turbo", ("No supported local runtime detected", "Groq needs no local model")
    )


def _has_cuda() -> bool:
    try:
        import torch
    except ImportError:
        return False
    return bool(torch.cuda.is_available())
