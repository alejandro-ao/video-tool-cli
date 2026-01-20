from __future__ import annotations

from .base import VideoProcessorBase
from .concatenation import ConcatenationMixin
from .content import ContentGenerationMixin
from .deployment import BunnyDeploymentMixin
from .download import DownloadMixin
from .editing import EditingMixin
from .file_management import FileManagementMixin
from .silence import SilenceProcessingMixin
from .transcript import TranscriptMixin
from .youtube import YouTubeDeploymentMixin


class VideoProcessor(
    EditingMixin,
    YouTubeDeploymentMixin,
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
