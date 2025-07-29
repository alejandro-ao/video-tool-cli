from mcp import tool
from pathlib import Path
import sys
import os

# Add the parent directory to the Python path to allow imports from the root of the project.
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from video_processor import VideoProcessor

@tool(
    name="remove_silences",
    description="Removes silent sections from MP4 videos in a specified directory.",
    args_schema={
        "input_dir": {
            "type": "string",
            "description": "The absolute path to the directory containing the MP4 files.",
            "required": True
        }
    }
)
def remove_silences(input_dir: str) -> str:
    """
    Removes silent sections from MP4 videos.

    Args:
        input_dir: The directory containing the video files.

    Returns:
        The path to the directory containing the processed videos.
    """
    processor = VideoProcessor(input_dir)
    processed_dir = processor.remove_silences()
    return processed_dir


@tool(
    name="concatenate_videos",
    description="Concatenates multiple MP4 videos in alphabetical order.",
    args_schema={
        "input_dir": {
            "type": "string",
            "description": "The absolute path to the directory containing the MP4 files.",
            "required": True
        },
        "output_filename": {
            "type": "string",
            "description": "Optional custom filename for the output video.",
            "required": False
        },
        "skip_reprocessing": {
            "type": "boolean",
            "description": "If True, skips video standardization.",
            "required": False
        }
    }
)
def concatenate_videos(input_dir: str, output_filename: str = None, skip_reprocessing: bool = False) -> str:
    """
    Concatenates multiple MP4 videos.

    Args:
        input_dir: The directory containing the video files.
        output_filename: Optional custom filename for the output video.
        skip_reprocessing: If True, skips video standardization.

    Returns:
        The path to the concatenated video.
    """
    processor = VideoProcessor(input_dir)
    concatenated_video_path = processor.concatenate_videos(output_filename, skip_reprocessing)
    return concatenated_video_path


@tool(
    name="generate_timestamps",
    description="Generates timestamp information for the video with chapters based on input videos.",
    args_schema={
        "input_dir": {
            "type": "string",
            "description": "The absolute path to the directory containing the MP4 files.",
            "required": True
        }
    }
)
def generate_timestamps(input_dir: str) -> dict:
    """
    Generates timestamp information for the video.

    Args:
        input_dir: The directory containing the video files.

    Returns:
        A dictionary containing the timestamp information.
    """
    processor = VideoProcessor(input_dir)
    timestamps = processor.generate_timestamps()
    return timestamps


@tool(
    name="generate_transcript",
    description="Generates VTT transcript using OpenAI's Whisper API.",
    args_schema={
        "video_path": {
            "type": "string",
            "description": "The absolute path to the video file.",
            "required": True
        }
    }
)
def generate_transcript(video_path: str) -> str:
    """
    Generates VTT transcript for a video file.

    Args:
        video_path: The path to the video file.

    Returns:
        The path to the transcript file.
    """
    # The VideoProcessor is initialized with the input directory of the video_path
    input_dir = str(Path(video_path).parent)
    processor = VideoProcessor(input_dir)
    transcript_path = processor.generate_transcript(video_path)
    return transcript_path


@tool(
    name="generate_description",
    description="Generates video description using LLM.",
    args_schema={
        "video_path": {
            "type": "string",
            "description": "The absolute path to the video file.",
            "required": True
        },
        "repo_url": {
            "type": "string",
            "description": "The URL of the repository.",
            "required": True
        },
        "transcript_path": {
            "type": "string",
            "description": "The absolute path to the transcript file.",
            "required": True
        }
    }
)
def generate_description(video_path: str, repo_url: str, transcript_path: str) -> str:
    """
    Generates video description.

    Args:
        video_path: The path to the video file.
        repo_url: The URL of the repository.
        transcript_path: The path to the transcript file.

    Returns:
        The path to the description file.
    """
    input_dir = str(Path(video_path).parent)
    processor = VideoProcessor(input_dir)
    description_path = processor.generate_description(video_path, repo_url, transcript_path)
    return description_path


@tool(
    name="generate_seo_keywords",
    description="Generates SEO keywords based on video description.",
    args_schema={
        "description_path": {
            "type": "string",
            "description": "The absolute path to the description file.",
            "required": True
        }
    }
)
def generate_seo_keywords(description_path: str) -> str:
    """
    Generates SEO keywords.

    Args:
        description_path: The path to the description file.

    Returns:
        The path to the keywords file.
    """
    input_dir = str(Path(description_path).parent)
    processor = VideoProcessor(input_dir)
    keywords_path = processor.generate_seo_keywords(description_path)
    return keywords_path
