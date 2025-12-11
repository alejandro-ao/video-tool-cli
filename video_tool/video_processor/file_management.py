from __future__ import annotations

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

from .constants import is_supported_video_file
from .shared import VideoFileClip, logger


class FileManagementMixin:
    """File discovery and metadata helpers."""

    def extract_duration_csv(self) -> str:
        """Process all supported video files and emit a metadata CSV."""
        output_csv = self.output_dir / "video_metadata.csv"
        with open(output_csv, "w", newline="", encoding="utf-8") as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow(["creation_date", "video_title", "duration_minutes"])

            for root, dirs, files in os.walk(self.input_dir):
                dirs[:] = [d for d in dirs if not d.endswith(".screenstudio")]
                for filename in files:
                    file_path = Path(root) / filename
                    if is_supported_video_file(file_path):
                        creation_date, video_title, duration_minutes = self._get_video_metadata(
                            str(file_path)
                        )
                        if creation_date:
                            csv_writer.writerow([creation_date, video_title, duration_minutes])
                            logger.info(f"Processed: {video_title}")

        logger.info(f"Metadata exported to {output_csv}")
        return str(output_csv)

    def _get_video_metadata(
        self, file_path: str
    ) -> Tuple[Optional[str], Optional[str], Optional[float]]:
        """Extract creation timestamp, stem, and duration in minutes."""
        try:
            creation_timestamp = os.path.getctime(file_path)
            creation_date = datetime.fromtimestamp(creation_timestamp).strftime(
                "%Y-%m-%d %H:%M:%S"
            )
            video_title = os.path.splitext(os.path.basename(file_path))[0]

            with self.suppress_external_output():
                try:
                    clip = VideoFileClip(file_path, audio=False, verbose=False)  # type: ignore[arg-type]
                except TypeError:
                    clip = VideoFileClip(file_path)

                try:
                    duration_seconds = clip.duration
                finally:
                    clip.close()

            duration_minutes = round(duration_seconds / 60, 2)
            return creation_date, video_title, duration_minutes
        except Exception as exc:  # pragma: no cover - surfaced via logging
            logger.error(f"Error processing file {file_path}: {exc}")
            return None, None, None

    def get_video_files(self, directory: Optional[str] = None) -> List[Path]:
        """Get all supported video files in the specified directory."""
        try:
            search_dir = Path(directory) if directory else self.input_dir
            input_path = search_dir.expanduser().resolve()
            logger.debug(f"Searching for video files in: {input_path}")

            if not input_path.exists() or not input_path.is_dir():
                raise ValueError(
                    f"Directory does not exist or is not a directory: {input_path}"
                )

            video_files = sorted(
                [f for f in input_path.iterdir() if f.is_file() and is_supported_video_file(f)]
            )
            logger.debug(
                f"Found {len(video_files)} video files: {[f.name for f in video_files]}"
            )

            if not video_files:
                logger.warning(f"No supported video files found in directory: {input_path}")
            return video_files
        except Exception as exc:
            logger.error(f"Error accessing directory {search_dir}: {exc}")
            raise

    def get_mp4_files(self, directory: Optional[str] = None) -> List[Path]:
        """
        Backwards-compatible alias for get_video_files.

        Historically this function only surfaced MP4 assets; it now returns all
        supported containers defined in SUPPORTED_VIDEO_SUFFIXES.
        """
        return self.get_video_files(directory)
