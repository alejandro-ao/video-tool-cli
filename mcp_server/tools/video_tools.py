from mcp.server.fastmcp import FastMCP
from pathlib import Path
import sys
import os
from pydantic import BaseModel, Field

# Remove manual sys.path modification and use proper package imports
# Add the parent directory to the Python path to allow imports from the root of the project.
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))
from video_tool import VideoProcessor

mcp = FastMCP("video_editor", log_level="ERROR", host="0.0.0.0", port=8000)


class DirectoryPath(BaseModel):
    """A model to represent a directory path."""
    path: str = Field(..., description="The absolute path to the directory.")


class ConcatenatedVideo(BaseModel):
    """A model to represent a concatenated video."""
    path: str = Field(..., description="The absolute path to the concatenated video.")


class TimestampInfo(BaseModel):
    """A model to represent timestamp information."""
    timestamps: dict = Field(..., description="A dictionary containing the timestamp information.")


class Transcript(BaseModel):
    """A model to represent a transcript file."""
    path: str = Field(..., description="The absolute path to the transcript file.")


class Description(BaseModel):
    """A model to represent a description file."""
    path: str = Field(..., description="The absolute path to the description file.")


class SeoKeywords(BaseModel):
    """A model to represent a keywords file."""
    path: str = Field(..., description="The absolute path to the keywords file.")

class CsvFile(BaseModel):
    """A model to represent a CSV file."""
    file_path: str = Field(..., description="Path to the generated CSV file")

class ReencodedVideo(BaseModel):
    """A model to represent a re-encoded video."""
    path: str = Field(..., description="The absolute path to the re-encoded video.")

class CompressedVideo(BaseModel):
    """A model to represent a compressed video."""
    path: str = Field(..., description="The absolute path to the compressed video.")


@mcp.tool()
def remove_silences(input_dir: str) -> DirectoryPath:
    """
    Removes silent sections from MP4 videos.

    Args:
        input_dir: The directory containing the video files.

    Returns:
        The path to the directory containing the processed videos.
    """
    processor = VideoProcessor(input_dir)
    processed_dir = processor.remove_silences()
    return DirectoryPath(path=processed_dir)


@mcp.tool()
def concatenate_videos(input_dir: str, output_filename: str = None, skip_reprocessing: bool = False) -> ConcatenatedVideo:
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
    return ConcatenatedVideo(path=concatenated_video_path)


@mcp.tool()
def generate_timestamps(input_dir: str) -> TimestampInfo:
    """
    Generates timestamp information for the video.

    Args:
        input_dir: The directory containing the video files.

    Returns:
        A dictionary containing the timestamp information.
    """
    processor = VideoProcessor(input_dir)
    timestamps = processor.generate_timestamps()
    return TimestampInfo(timestamps=timestamps)


@mcp.tool()
def generate_transcript(video_path: str) -> Transcript:
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
    return Transcript(path=transcript_path)


@mcp.tool()
def generate_description(video_path: str, repo_url: str, transcript_path: str) -> Description:
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
    return Description(path=description_path)


@mcp.tool()
def extract_duration_csv(input_dir: str) -> CsvFile:
    """
    Process all MP4 files in a directory and its subdirectories, extract their creation date,
    video title, and duration in minutes, then export this information to a CSV file.
    Directories ending with .screenstudio are excluded from processing.

    Args:
        input_dir: The directory containing the video files.

    Returns:
        The path to the generated CSV file.
    """
    processor = VideoProcessor(input_dir)
    csv_path = processor.extract_duration_csv()
    return CsvFile(file_path=csv_path)


@mcp.tool()
def generate_seo_keywords(description_path: str) -> SeoKeywords:
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
    return SeoKeywords(path=keywords_path)


@mcp.tool()
def reencode_to_match(source_video_path: str, reference_video_path: str, output_filename: str | None = None) -> ReencodedVideo:
    """
    Re-encode source video A to match the encoding of reference video B.

    Args:
        source_video_path: Path to the source video (A).
        reference_video_path: Path to the reference video (B).
        output_filename: Optional output filename for the re-encoded video.

    Returns:
        The path to the re-encoded MP4 file.
    """
    input_dir = str(Path(source_video_path).parent)
    processor = VideoProcessor(input_dir)
    output_path = processor.match_video_encoding(source_video_path, reference_video_path, output_filename)
    return ReencodedVideo(path=output_path)


@mcp.tool()
def compress_video(video_path: str, output_filename: str | None = None, codec: str = "auto", crf: int = 23, preset: str = "medium") -> CompressedVideo:
    """
    Compress an MP4 video to reduce file size while maintaining quality.

    Args:
        video_path: Path to the input video file.
        output_filename: Optional output filename for the compressed video.
        codec: Video codec to use ('h264', 'h265', or 'auto' for best available).
        crf: Constant Rate Factor (18-28, lower = higher quality, 23 is default).
        preset: Encoding preset ('ultrafast', 'fast', 'medium', 'slow', 'veryslow').

    Returns:
        The path to the compressed MP4 file.
    """
    input_dir = str(Path(video_path).parent)
    processor = VideoProcessor(input_dir)
    output_path = processor.compress_video(video_path, output_filename, codec, crf, preset)
    return CompressedVideo(path=output_path)
