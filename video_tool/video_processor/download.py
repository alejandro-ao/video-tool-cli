"""Download mixin for VideoProcessor."""

from __future__ import annotations

import subprocess
from pathlib import Path

from loguru import logger


class DownloadMixin:
    """YouTube/URL video download helpers."""

    def download_video(self, url: str, output_template: str | Path) -> Path:
        """Download video from URL using yt-dlp.

        Args:
            url: Video URL to download
            output_template: Output file path or template

        Returns:
            Path to output template
        """
        output_path = Path(output_template)
        if output_path.exists() and output_path.is_dir():
            output_path = output_path / "%(title)s.%(ext)s"

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_template = str(output_path)

        logger.info(f"Downloading video from {url}")
        logger.info(f"Output template: {output_template}")

        cmd = [
            "yt-dlp",
            "--quiet",
            "--no-warnings",
            "-f",
            "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "-o",
            output_template,
            "--merge-output-format",
            "mp4",
            url,
        ]
        subprocess.run(cmd, check=True)
        return output_path
