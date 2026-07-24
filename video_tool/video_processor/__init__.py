"""Video processing package.

Only the VideoProcessor facade is part of the public API. Each submodule
imports its own third-party dependencies directly; patch them at the
submodule that uses them (e.g. ``video_tool.video_processor.transcript.VideoFileClip``).
"""

from .processor import VideoProcessor

__all__ = ["VideoProcessor"]
