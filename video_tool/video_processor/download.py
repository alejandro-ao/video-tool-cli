"""Download mixin for VideoProcessor."""

from __future__ import annotations

import subprocess
from pathlib import Path

from .shared import logger


class DownloadMixin:
    """YouTube/URL video download helpers."""

    def download_video(
        self, url: str, output_dir: Path, filename: str | None = None
    ) -> Path:
        """Download video from URL using yt-dlp.

        Args:
            url: Video URL to download
            output_dir: Directory to save the video
            filename: Optional output filename (uses video title if not specified)

        Returns:
            Path to downloaded file or output directory
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        if filename:
            if not filename.endswith(".mp4"):
                filename += ".mp4"
            output_template = str(output_dir / filename)
        else:
            output_template = str(output_dir / "%(title)s.%(ext)s")

        logger.info(f"Downloading video from {url}")
        logger.info(f"Output directory: {output_dir}")

        cmd = [
            "yt-dlp",
            "-f",
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "-o",
            output_template,
            "--merge-output-format",
            "mp4",
            url,
        ]
        subprocess.run(cmd, check=True)
        return output_dir
