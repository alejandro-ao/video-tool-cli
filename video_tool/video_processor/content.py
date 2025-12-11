from __future__ import annotations

import json
from pathlib import Path
from string import Template
from textwrap import dedent
from typing import Optional

from pydantic import BaseModel, Field

from .constants import SUPPORTED_VIDEO_SUFFIXES
from .shared import logger


class SummaryResponse(BaseModel):
    """Structured representation of a video summary."""

    what_this_video_is_about: str = Field(description="Overview of the video's main topic.")
    why_this_topic_matters: str = Field(description="Explanation of the real-world importance.")
    key_points_covered: list[str] = Field(
        description="Bullet list of 4-7 core technical points covered.",
        default_factory=list,
    )
    what_is_built: str = Field(description="Description of what is implemented in the video.")
    actionable_insights: list[str] = Field(
        description="Practical skills or actions viewers can take away.",
        default_factory=list,
    )
    who_this_video_is_for: str = Field(
        description="Intended audience and skill level for the content."
    )
    further_research: list[str] = Field(
        description="Topics to explore after watching.", default_factory=list
    )
    seo_friendly_keywords: list[str] = Field(
        description="10-20 comma-separated keywords.", default_factory=list
    )


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
                videos = []
                for suffix in SUPPORTED_VIDEO_SUFFIXES:
                    videos.extend(Path(self.input_dir).glob(f"*{suffix}"))
                videos = sorted(videos)
                if videos:
                    video_path = str(videos[0])
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

    def generate_context_cards(
        self,
        transcript_path: Optional[str] = None,
        output_path: Optional[str] = None,
    ) -> str:
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

            output_file = Path(output_path) if output_path else self.output_dir / "context-cards.md"
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as file:
                file.write(response.content)

            logger.info(f"Context cards generated successfully: {output_file}")
            return str(output_file)
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

    def generate_summary(
        self,
        transcript_path: Optional[str] = None,
        *,
        output_path: Optional[str] = None,
        config: Optional[dict] = None,
    ) -> str:
        """Generate a structured technical summary from a transcript."""

        summary_config = {
            "enabled": True,
            "length": "medium",
            "difficulty": "intermediate",
            "include_keywords": True,
            "target_audience": "AI/ML engineers and developers in a private community",
            "output_format": "markdown",
        }
        if config:
            summary_config.update(config)

        if not summary_config.get("enabled", True):
            logger.info("Summary generation disabled via configuration; skipping step.")
            return ""

        transcript_file = (
            Path(transcript_path)
            if transcript_path
            else self.output_dir / "transcript.vtt"
        )

        if not transcript_file.exists():
            logger.error(f"Transcript file not found for summary generation: {transcript_file}")
            return ""

        try:
            transcript = transcript_file.read_text(encoding="utf-8")
        except OSError as exc:
            logger.error(f"Unable to read transcript for summary generation: {exc}")
            return ""

        output_format = str(summary_config.get("output_format", "markdown")).lower().strip()
        if output_format not in {"markdown", "json"}:
            logger.warning(
                f"Unsupported summary output_format '{output_format}', defaulting to markdown."
            )
            output_format = "markdown"

        include_keywords = bool(summary_config.get("include_keywords", True))
        difficulty = summary_config.get("difficulty", "intermediate")
        length = summary_config.get("length", "medium")
        target_audience = summary_config.get(
            "target_audience", "AI/ML engineers and developers in a private community"
        )

        summary_dir = self.output_dir / "summaries"
        resolved_output_path = Path(output_path) if output_path else summary_dir / (
            f"{transcript_file.stem}_summary.{ 'json' if output_format == 'json' else 'md'}"
        )
        resolved_output_path.parent.mkdir(parents=True, exist_ok=True)

        system_message = dedent(
            f"""
            You are a specialized summary-generation agent integrated into a video-processing pipeline for a private community of AI/ML engineers and developers. Your role is to produce a high-quality, structured summary of a technical video based solely on the transcript. The audience is already technically literate. Do not explain basic concepts unless the video does; instead, emphasize the technical depth, tools, frameworks, and skills covered.

            Follow this structure exactly:
            1. What This Video Is About
            2. Why This Topic Matters
            3. Key Points Covered in the Video
            4. What Is Built in This Video
            5. Actionable Insights / Skills You’ll Gain
            6. Who This Video Is For
            7. Further Research / Next Steps
            8. SEO-Friendly Keywords

            Additional rules:
            - Be accurate and avoid hallucinations.
            - Only use information present in the transcript.
            - The tone should be clear, concise, and professional.
            - Calibrate the level of detail for a {difficulty} audience and aim for a {length} summary.
            - Target audience: {target_audience}.
            - If SEO keywords are disabled, still include section 8 and state that keywords are omitted per configuration.
            """
        ).strip()

        keyword_instruction = (
            "Include 10-20 SEO-friendly keywords as a comma-separated line."
            if include_keywords
            else "Do not invent SEO keywords; note that they are omitted per configuration."
        )

        user_message = dedent(
            f"""
            Generate the summary using the transcript below.
            {keyword_instruction}

            <TRANSCRIPT>
            {transcript}
            </TRANSCRIPT>
            """
        ).strip()

        try:
            if output_format == "json":
                response = self._invoke_openai_chat_structured_output(
                    model="gpt-5",
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": user_message},
                    ],
                    schema=SummaryResponse,
                    temperature=0.3,
                )

                summary_payload = response.dict()
                if not include_keywords:
                    summary_payload["seo_friendly_keywords"] = []

                resolved_output_path.write_text(
                    json.dumps(summary_payload, indent=2), encoding="utf-8"
                )
            else:
                response = self._invoke_openai_chat(
                    model="gpt-5",
                    messages=[
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=0.3,
                )

                summary_content = response.content
                if not isinstance(summary_content, str):
                    summary_content = str(summary_content)

                resolved_output_path.write_text(summary_content, encoding="utf-8")

            logger.info(f"Summary generated successfully: {resolved_output_path}")
            return str(resolved_output_path)
        except Exception as exc:
            logger.error(f"Error generating summary: {exc}")
            return ""
