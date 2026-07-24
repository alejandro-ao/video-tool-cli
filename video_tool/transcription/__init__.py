"""Multi-backend local and remote transcription support."""

from .base import MissingBackendDependency, TranscriptionBackend, TranscriptionError
from .models import TranscriptionModel, TranscriptResult, TranscriptSegment
from .recommendation import Recommendation, recommend_model
from .registry import list_models, resolve_model
from .service import TranscriptionService, render_vtt

__all__ = [
    "MissingBackendDependency",
    "Recommendation",
    "TranscriptResult",
    "TranscriptSegment",
    "TranscriptionBackend",
    "TranscriptionError",
    "TranscriptionModel",
    "TranscriptionService",
    "list_models",
    "recommend_model",
    "render_vtt",
    "resolve_model",
]
