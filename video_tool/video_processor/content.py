from __future__ import annotations

import json
from pathlib import Path
from string import Template
from textwrap import dedent
from typing import Optional

from .shared import logger


class ContentGenerationMixin:
    """LLM-backed content generation helpers."""

    def generate_description(
        self,
        video_path: Optional[str] = None,
        repo_url: Optional[str] = None,
        transcript_path: Optional[str] = None,
        output_path: Optional[str] = None,
        timestamps_path: Optional[str] = None,
    ) -> str:
        """Generate video description using LLM."""
        if video_path is None:
            candidate = self._find_existing_output()
            if candidate:
                video_path = str(candidate)
            else:
                mp4s = list(Path(self.input_dir).glob("*.mp4"))
                if mp4s:
                    video_path = str(mp4s[0])
                else:
                    logger.error("No video file found for description generation")
                    raise FileNotFoundError("No video file found for description generation")

        if transcript_path is None:
            transcript_path = str(self.output_dir / "transcript.vtt")

        transcript_file = Path(transcript_path)
        if not transcript_file.exists():
            logger.error("Transcript file not found for description generation")
            return ""

        repo_url = repo_url or ""

        with open(transcript_file) as file:
            transcript = file.read()

        prompt = self.prompts["generate_description"].format(transcript=transcript)

        response = self._invoke_openai_chat(
            model="gpt-5", messages=[{"role": "user", "content": prompt}]
        )

        links = [
            {"url": repo_url, "description": "Code from the video"},
            {
                "url": "https://aibootcamp.dev",
                "description": "🚀 Complete AI Engineer Bootcamp",
            },
            {
                "url": "https://link.alejandro-ao.com/l83gNq",
                "description": "❤️ Buy me a coffee... or a beer (thanks)",
            },
            {
                "url": "https://link.alejandro-ao.com/HrFKZn",
                "description": "💬 Join the Discord Help Server",
            },
            {
                "url": "https://link.alejandro-ao.com/AIIguB",
                "description": "✉️ Get the news from the channel and AI Engineering",
            },
        ]

        # Handle timestamps (optional)
        timestamps = None
        timestamp_list = None

        if timestamps_path:
            resolved_timestamps_path = Path(timestamps_path)
        else:
            resolved_timestamps_path = self.output_dir / "timestamps.json"

        if resolved_timestamps_path.exists():
            try:
                with open(resolved_timestamps_path) as file:
                    timestamps = json.load(file)[0]["timestamps"]
                timestamp_list = "\n".join(
                    f'{timestamp["start"]} - {timestamp["title"]}' for timestamp in timestamps
                )
                logger.info(f"Using timestamps from: {resolved_timestamps_path}")
            except Exception as exc:
                logger.warning(f"Could not load timestamps from {resolved_timestamps_path}: {exc}")
                timestamps = None
                timestamp_list = None
        else:
            logger.info("No timestamps file found, generating description without timestamps")

        link_list = "\n".join(f'- {link["description"]}: {link["url"]}' for link in links)

        # Build template with or without timestamps section
        if timestamp_list:
            template = Template(
                dedent(
                    """
                    # $title

                    $content

                    ## Links
                    $links

                    ## Timestamps
                    $timestamps
                    """
                )
            )
            description = template.substitute(
                title=Path(video_path).stem,
                content=response.content,
                links=link_list,
                timestamps=timestamp_list,
            )
        else:
            template = Template(
                dedent(
                    """
                    # $title

                    $content

                    ## Links
                    $links
                    """
                )
            )
            description = template.substitute(
                title=Path(video_path).stem,
                content=response.content,
                links=link_list,
            )

        polish_description_prompt = self.prompts["polish_description"].format(
            description=description
        )

        polished_description_response = self._invoke_openai_chat(
            model="gpt-5",
            messages=[{"role": "user", "content": polish_description_prompt}],
        )

        try:
            polished_description = polished_description_response.content
            if not isinstance(polished_description, str):
                polished_description = str(polished_description)
        except Exception as exc:
            if callable(logger):
                logger()
            logger.error(f"Error extracting polished description: {exc}")
            return ""

        resolved_output_path = Path(output_path) if output_path else self.output_dir / "description.md"
        resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(resolved_output_path, "w") as file:
                file.write(polished_description)
        except Exception as exc:
            if callable(logger):
                logger()
            logger.error(f"Error writing description file: {exc}")
            return ""

        return str(resolved_output_path)

    def generate_context_cards(self, transcript_path: Optional[str] = None) -> str:
        """Generate Markdown file with suggested YouTube cards and resource mentions."""
        try:
            transcript_file = (
                Path(transcript_path)
                if transcript_path
                else self.output_dir / "transcript.vtt"
            )

            if not transcript_file.exists():
                logger.error(f"Transcript file not found: {transcript_file}")
                return ""

            with open(transcript_file) as file:
                transcript = file.read()
        except Exception as exc:
            logger.error(f"Error reading transcript for context cards: {exc}")
            return ""

        try:
            prompt = self.prompts["generate_context_cards"].format(transcript=transcript)

            response = self._invoke_openai_chat(
                model="gpt-4o",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1500,
                temperature=0.4,
            )

            output_path = self.output_dir / "context-cards.md"
            with open(output_path, "w") as file:
                file.write(response.content)

            logger.info(f"Context cards generated successfully: {output_path}")
            return str(output_path)
        except Exception as exc:
            logger.error(f"Error generating context cards: {exc}")
            return ""

    def generate_seo_keywords(self, description_path: str) -> str:
        """Generate SEO keywords based on video description."""
        try:
            with open(description_path) as file:
                description = file.read()
        except FileNotFoundError:
            if callable(logger):
                logger()
            logger.error(f"Description file not found: {description_path}")
            return ""
        except Exception as exc:
            if callable(logger):
                logger()
            logger.error(f"Error reading description file: {exc}")
            return ""

        try:
            prompt = self.prompts["generate_seo_keywords"].format(
                description=description
            )

            response = self._invoke_openai_chat(
                model="gpt-5", messages=[{"role": "user", "content": prompt}]
            )

            output_path = Path(description_path).parent / "keywords.txt"

            with open(output_path, "w") as file:
                file.write(response.content)

            return str(output_path)
        except Exception as exc:
            if callable(logger):
                logger()
            logger.error(f"Error generating SEO keywords: {exc}")
            return ""

    def generate_linkedin_post(self, transcript_path: str, output_path: Optional[str] = None) -> str:
        """Generate LinkedIn post based on video transcript."""
        try:
            with open(transcript_path) as file:
                transcript = file.read()
        except FileNotFoundError:
            logger.error(f"Transcript file not found: {transcript_path}")
            raise
        except Exception as exc:
            logger.error(f"Error reading transcript file: {exc}")
            raise

        try:
            prompt = self.prompts["generate_linkedin_post"].format(transcript=transcript)

            response = self._invoke_openai_chat(
                model="gpt-5",
                messages=[{"role": "user", "content": prompt}],
            )

            resolved_output_path = Path(output_path) if output_path else self.output_dir / "linkedin_post.md"
            resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(resolved_output_path, "w") as file:
                file.write(response.content)

            logger.info(f"LinkedIn post generated successfully: {resolved_output_path}")
            return str(resolved_output_path)
        except Exception as exc:
            logger.error(f"Error generating LinkedIn post: {exc}")
            raise

    def generate_twitter_post(self, transcript_path: str, output_path: Optional[str] = None) -> str:
        """Generate Twitter post based on video transcript."""
        try:
            with open(transcript_path) as file:
                transcript = file.read()
        except FileNotFoundError:
            logger.error(f"Transcript file not found: {transcript_path}")
            raise
        except Exception as exc:
            logger.error(f"Error reading transcript file: {exc}")
            raise

        try:
            prompt = self.prompts["generate_twitter_post"].format(transcript=transcript)

            response = self._invoke_openai_chat(
                model="gpt-5",
                messages=[{"role": "user", "content": prompt}],
            )

            resolved_output_path = Path(output_path) if output_path else self.output_dir / "twitter_post.md"
            resolved_output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(resolved_output_path, "w") as file:
                file.write(response.content)

            logger.info(f"Twitter post generated successfully: {resolved_output_path}")
            return str(resolved_output_path)
        except Exception as exc:
            logger.error(f"Error generating Twitter post: {exc}")
            raise
