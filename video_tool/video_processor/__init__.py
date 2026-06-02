import warnings

from loguru import logger
from moviepy import VideoFileClip

# pydub currently emits invalid-escape SyntaxWarnings on Python 3.14 during
# import. They are third-party warnings, not actionable for video-tool users.
warnings.filterwarnings(
    "ignore",
    message=r".*invalid escape sequence.*",
    category=SyntaxWarning,
)
from pydub import AudioSegment
from pydub.silence import detect_nonsilent
from groq import Groq
from openai import OpenAI
import requests

from .processor import VideoProcessor

__all__ = [
    "VideoProcessor",
    "VideoFileClip",
    "AudioSegment",
    "detect_nonsilent",
    "OpenAI",
    "Groq",
    "logger",
    "requests",
]
