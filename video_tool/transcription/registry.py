"""Known transcription models and backend factory."""

from __future__ import annotations

from collections.abc import Callable

from .base import TranscriptionBackend, TranscriptionError
from .models import TranscriptionModel

MODELS: tuple[TranscriptionModel, ...] = (
    TranscriptionModel(
        "groq/whisper-large-v3-turbo",
        "groq",
        "whisper-large-v3-turbo",
        False,
        True,
        ("darwin", "linux", "win32"),
        None,
        "Fast hosted Whisper transcription",
    ),
    TranscriptionModel(
        "mlx/parakeet-tdt-0.6b-v2",
        "mlx-parakeet",
        "mlx-community/parakeet-tdt-0.6b-v2",
        True,
        False,
        ("darwin",),
        "transcription-mlx",
        "Fast English transcription on Apple Silicon",
    ),
    TranscriptionModel(
        "mlx/whisper-large-v3-turbo",
        "mlx-whisper",
        "mlx-community/whisper-large-v3-turbo",
        True,
        True,
        ("darwin",),
        "transcription-mlx",
        "Multilingual Whisper optimized for Apple Silicon",
    ),
    TranscriptionModel(
        "faster-whisper/large-v3-turbo",
        "faster-whisper",
        "large-v3-turbo",
        True,
        True,
        ("darwin", "linux", "win32"),
        "transcription-faster-whisper",
        "Portable CTranslate2 Whisper",
    ),
    TranscriptionModel(
        "transformers/whisper-large-v3-turbo",
        "transformers",
        "openai/whisper-large-v3-turbo",
        True,
        True,
        ("darwin", "linux", "win32"),
        "transcription-transformers",
        "Whisper using the Transformers pipeline",
    ),
    TranscriptionModel(
        "nemo/parakeet-tdt-0.6b-v2",
        "nemo",
        "nvidia/parakeet-tdt-0.6b-v2",
        True,
        False,
        ("linux",),
        "transcription-nemo",
        "Native NVIDIA NeMo Parakeet",
    ),
)

_MODEL_BY_ID = {item.id: item for item in MODELS}
_DEFAULT_BY_BACKEND = {item.backend: item for item in MODELS}


def list_models() -> tuple[TranscriptionModel, ...]:
    """Return all supported models."""
    return MODELS


def resolve_model(model_id: str | None, backend: str | None = None) -> TranscriptionModel:
    """Resolve a public model ID or a backend default."""
    if model_id and model_id != "auto":
        try:
            return _MODEL_BY_ID[model_id]
        except KeyError as exc:
            choices = ", ".join(_MODEL_BY_ID)
            raise TranscriptionError(f"Unknown transcription model '{model_id}'. Choose one of: {choices}") from exc
    if backend and backend != "auto":
        try:
            return _DEFAULT_BY_BACKEND[backend]
        except KeyError as exc:
            raise TranscriptionError(f"Unknown transcription backend '{backend}'") from exc
    raise TranscriptionError("A transcription model must be selected before resolving the backend")


def create_backend(name: str, *, groq_client: object | None = None) -> TranscriptionBackend:
    """Construct a backend without importing unrelated optional runtimes."""
    from .backends.faster_whisper import FasterWhisperBackend
    from .backends.groq import GroqBackend
    from .backends.mlx_parakeet import MlxParakeetBackend
    from .backends.mlx_whisper import MlxWhisperBackend
    from .backends.nemo import NemoBackend
    from .backends.transformers import TransformersBackend

    factories: dict[str, Callable[[], TranscriptionBackend]] = {
        "groq": lambda: GroqBackend(groq_client),
        "mlx-parakeet": MlxParakeetBackend,
        "mlx-whisper": MlxWhisperBackend,
        "faster-whisper": FasterWhisperBackend,
        "transformers": TransformersBackend,
        "nemo": NemoBackend,
    }
    try:
        return factories[name]()
    except KeyError as exc:
        raise TranscriptionError(f"Unknown transcription backend '{name}'") from exc
