from __future__ import annotations

from .base import VideoProcessorBase
from .concatenation import ConcatenationMixin
from .content import ContentGenerationMixin
from .deployment import BunnyDeploymentMixin
from .download import DownloadMixin
from .file_management import FileManagementMixin
from .silence import SilenceProcessingMixin
from .transcript import TranscriptMixin


class VideoProcessor(
    BunnyDeploymentMixin,
    ContentGenerationMixin,
    TranscriptMixin,
    ConcatenationMixin,
    SilenceProcessingMixin,
    DownloadMixin,
    FileManagementMixin,
    VideoProcessorBase,
):
    """Facade combining all processing capabilities."""

    __slots__ = ()
