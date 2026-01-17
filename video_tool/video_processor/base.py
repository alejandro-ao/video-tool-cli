from __future__ import annotations

import os
import re
import unicodedata
from contextlib import contextmanager, redirect_stderr, redirect_stdout
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Type, TypeVar, Union

import yaml
from openai import OpenAI
from pydantic import BaseModel

from video_tool.config import get_llm_config

from .shared import Groq, logger

StructuredResponse = TypeVar("StructuredResponse", bound=BaseModel)


class VideoProcessorBase:
    """Core configuration and shared helpers for the video processor workflow."""

    def __init__(
        self,
        input_dir: str,
        video_title: Optional[str] = None,
        show_external_logs: bool = False,
        output_dir: Optional[str] = None,
    ):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir) if output_dir else self.input_dir / "output"
        # Note: output_dir is created lazily when needed, not in __init__
        self.video_title = video_title.strip() if video_title else None
        self.show_external_logs = show_external_logs
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
        from video_tool.logging_config import configure_logging

        configure_logging(verbose=self.show_external_logs)

    def _quiet_subprocess_kwargs(self) -> Dict[str, object]:
        """Return subprocess kwargs that suppress stdout/stderr unless verbose logging is enabled."""
        if self.show_external_logs:
            return {}
        return {"capture_output": True, "text": True}

    @contextmanager
    def suppress_external_output(self):
        """Silence STDOUT/STDERR noise from third-party tooling unless verbose logging is enabled."""
        if self.show_external_logs:
            yield
            return

        with open(os.devnull, "w") as devnull:
            with redirect_stdout(devnull), redirect_stderr(devnull):
                yield

    def _get_openai_client(self, command: str) -> OpenAI:
        """Return an OpenAI client configured for the given command."""
        llm_config = get_llm_config(command)
        return OpenAI(base_url=llm_config.base_url)

    def _invoke_openai_chat(
        self,
        *,
        command: str,
        messages: List[Dict[str, str]],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Execute a chat completion request using the OpenAI SDK."""
        client = self._get_openai_client(command)
        llm_config = get_llm_config(command)

        kwargs: Dict[str, Union[str, float, int, List]] = {
            "model": llm_config.model,
            "messages": messages,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_completion_tokens"] = max_tokens

        response = client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    def _invoke_openai_chat_structured_output(
        self,
        *,
        command: str,
        messages: List[Dict[str, str]],
        schema: Type[StructuredResponse],
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> StructuredResponse:
        """Execute a chat request that returns structured output defined by the schema."""
        client = self._get_openai_client(command)
        llm_config = get_llm_config(command)

        kwargs: Dict[str, Union[str, float, int, List, Type]] = {
            "model": llm_config.model,
            "messages": messages,
            "response_format": schema,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        if max_tokens is not None:
            kwargs["max_completion_tokens"] = max_tokens

        response = client.beta.chat.completions.parse(**kwargs)
        return response.choices[0].message.parsed
