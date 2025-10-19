from __future__ import annotations

import base64
import json
from pathlib import Path
from string import Template
from textwrap import dedent
from typing import Optional

import openai

from .shared import logger


class ContentGenerationMixin:
    """LLM-backed content generation helpers."""

    @staticmethod
    def _coerce_image_tool_size(size: str) -> str:
        """Map user-provided dimensions to supported OpenAI image tool sizes."""
        normalized = size.strip().lower()
        if normalized == "":
            raise ValueError("Image size must be specified in the format WIDTHxHEIGHT or 'auto'.")

        allowed_sizes = {"1024x1024", "1024x1536", "1536x1024", "auto"}
        if normalized in allowed_sizes:
            return normalized

        if "x" not in normalized:
            raise ValueError("Image size must be specified in the format WIDTHxHEIGHT or 'auto'.")

        try:
            width_str, height_str = normalized.split("x", 1)
            width = int(width_str)
            height = int(height_str)
        except (ValueError, TypeError):
            raise ValueError("Image size must be specified in the format WIDTHxHEIGHT or 'auto'.")

        if width <= 0 or height <= 0:
            raise ValueError("Image dimensions must be positive integers.")

        if width == height:
            mapped = "1024x1024"
        elif width > height:
            mapped = "1536x1024"
        else:
            mapped = "1024x1536"

        logger.info(
            f"Requested size '{size}' not supported; using '{mapped}' to match OpenAI constraints."
        )
        return mapped

    def generate_thumbnail(
        self,
        *,
        prompt: str,
        size: str = "1280x720",
        output_path: Optional[str] = None,
        model: str = "gpt-5",
    ) -> str:
        """Generate a thumbnail image using the OpenAI image generation endpoint."""
        if not prompt or not prompt.strip():
            raise ValueError("Prompt is required to generate a thumbnail.")
        
        json_prompt = dedent("""
        prompt: "{prompt}",
        style: "cartoon, vector art, clean lines, bright colors, modern UI aesthetic",
        lighting: "soft and even lighting, slightly glowing highlights for depth",
        composition: "balanced, central focus on the map layout with space for title text at the top or center"
        background: "smooth gradient transitioning from deep black to a slightly bright, complementary color (such as cyan, blue, or teal)"
        """).format(prompt=prompt).strip()

        normalized_size = size.strip().lower()
        coerced_size = self._coerce_image_tool_size(normalized_size)
        try:
            response = openai.responses.create(
                model=model,
                input=json_prompt.strip(),
                tools=[
                    {
                        "type": "image_generation",
                        "size": coerced_size,
                        "quality": "high",
                        "background": "transparent",
                    }
                ],
            )
        except Exception as exc:
            logger.error(f"Error generating thumbnail with OpenAI: {exc}")
            raise

        image_chunks = []
        for output in getattr(response, "output", []) or []:
            if getattr(output, "type", None) == "image_generation_call":
                image_chunks.append(getattr(output, "result", None))

        if not image_chunks or not image_chunks[0]:
            logger.error("OpenAI image generation response did not include image data.")
            raise RuntimeError("No image data returned for thumbnail generation.")

        try:
            image_bytes = base64.b64decode(image_chunks[0])
        except Exception as exc:
            logger.error(f"Failed to decode thumbnail image data: {exc}")
            raise

        if output_path:
            resolved_output = Path(output_path).expanduser().resolve()
        else:
            self.output_dir.mkdir(parents=True, exist_ok=True)
            resolved_output = self._resolve_unique_output_path("thumbnail.png")

        resolved_output.parent.mkdir(parents=True, exist_ok=True)

        if not resolved_output.suffix:
            resolved_output = resolved_output.with_suffix(".png")

        with open(resolved_output, "wb") as file:
            file.write(image_bytes)

        logger.info(f"Thumbnail generated successfully: {resolved_output}")
        return str(resolved_output)

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
