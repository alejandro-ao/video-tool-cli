from __future__ import annotations

import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Optional

import yaml

from .shared import Groq, OpenAI, logger


class VideoProcessorBase:
    """Core configuration and shared helpers for the video processor workflow."""

    def __init__(self, input_dir: str, video_title: Optional[str] = None):
        self.input_dir = Path(input_dir)
        self.output_dir = self.input_dir / "output"
        self.output_dir.mkdir(exist_ok=True)
        self.video_title = video_title.strip() if video_title else None
        self.client = OpenAI()
        self.groq = Groq()
        self.prompts = self._load_prompts()
        self.setup_logging()
        self._preferred_output_filename = (
            self._sanitize_filename(self.video_title)
            if self.video_title
            else None
        )
        self.last_output_path: Optional[Path] = None

    def _sanitize_filename(self, candidate: Optional[str]) -> Optional[str]:
        """Sanitize a user provided title for safe filesystem usage."""
        if not candidate:
            return None

        normalized = unicodedata.normalize("NFKD", candidate)
        ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
        ascii_only = re.sub(r"[\\/*?:\"<>|]", "", ascii_only)
        ascii_only = re.sub(r"\s+", " ", ascii_only).strip()

        if not ascii_only:
            ascii_only = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

        if not ascii_only.lower().endswith(".mp4"):
            ascii_only = f"{ascii_only}.mp4"

        return ascii_only

    def _resolve_unique_output_path(self, filename: str) -> Path:
        """Ensure the output filename does not overwrite an existing file."""
        output_path = self.output_dir / filename
        if not output_path.exists():
            return output_path

        stem = output_path.stem
        suffix = output_path.suffix or ".mp4"
        counter = 1

        while True:
            candidate = self.output_dir / f"{stem}_{counter}{suffix}"
            if not candidate.exists():
                logger.warning(
                    f"Output file {output_path.name} exists, using {candidate.name} instead"
                )
                return candidate
            counter += 1

    def _determine_output_filename(self, requested_filename: Optional[str]) -> str:
        """Determine the appropriate output filename based on priority order."""
        sanitized_requested = self._sanitize_filename(requested_filename)
        if sanitized_requested:
            return sanitized_requested
        if self._preferred_output_filename:
            return self._preferred_output_filename
        return f"{datetime.now().strftime('%Y-%m-%d')}_concatenated.mp4"

    def _find_existing_output(self) -> Optional[Path]:
        """Locate an existing concatenated video produced during this session."""
        if self.last_output_path and self.last_output_path.exists():
            return self.last_output_path

        search_roots = [self.output_dir, self.input_dir]

        if self._preferred_output_filename:
            stem = Path(self._preferred_output_filename).stem
            for root in search_roots:
                preferred = root / self._preferred_output_filename
                if preferred.exists():
                    return preferred

                matches = sorted(
                    root.glob(f"{stem}_*.mp4"),
                    key=lambda p: p.stat().st_mtime,
                )
                if matches:
                    return matches[-1]

        for root in search_roots:
            legacy_candidate = root / "concatenated_video.mp4"
            if legacy_candidate.exists():
                return legacy_candidate

        return None

    def _load_prompts(self):
        """Load prompts from the YAML file."""
        prompts_path = Path(__file__).resolve().parent.parent / "prompts.yaml"
        with open(prompts_path) as f:
            return yaml.safe_load(f)

    def setup_logging(self):
        logger.add(
            "video_processor.log",
            rotation="1 day",
            retention="1 week",
            level="INFO",
        )
