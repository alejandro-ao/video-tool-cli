from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

import requests
from requests import Response

from .shared import logger


class BunnyDeploymentMixin:
    """Handle Bunny.net Stream uploads and metadata updates."""

    _API_BASE = "https://video.bunnycdn.com"

    def deploy_to_bunny(
        self,
        video_path: str,
        *,
        library_id: Optional[str] = None,
        access_key: Optional[str] = None,
        collection_id: Optional[str] = None,
        video_title: Optional[str] = None,
        chapters: Optional[Sequence[Dict[str, str]]] = None,
        transcript_path: Optional[str] = None,
        caption_language: Optional[str] = None,
    ) -> Optional[Dict[str, str]]:
        """Upload the final video to Bunny Stream and attach chapters/captions."""
        video_file = Path(video_path)
        if not video_file.exists():
            logger.error(f"Bunny upload aborted, video file missing: {video_path}")
            return None

        library = (library_id or os.getenv("BUNNY_LIBRARY_ID") or "").strip()
        access = (access_key or os.getenv("BUNNY_ACCESS_KEY") or "").strip()
        collection = (collection_id or os.getenv("BUNNY_COLLECTION_ID") or "").strip()
        caption_lang = (
            caption_language
            or os.getenv("BUNNY_CAPTION_LANGUAGE")
            or "en"
        ).strip() or "en"

        if not library or not access:
            logger.error(
                "Bunny upload skipped: BUNNY_LIBRARY_ID and BUNNY_ACCESS_KEY are required."
            )
            return None

        title = (
            (video_title or "").strip()
            or (self.video_title or "").strip()
            or video_file.stem
        )

        chapters_payload = self._prepare_chapters(chapters)
        transcript_file = self._resolve_transcript(transcript_path)

        create_response = self._create_video_entry(
            library=library,
            access_key=access,
            title=title,
            collection_id=collection or None,
        )
        if not create_response:
            return None

        video_id = (
            str(create_response.get("videoId") or create_response.get("guid") or "").strip()
        )
        if not video_id:
            logger.error("Bunny video creation response missing videoId/guid.")
            return None

        if not self._upload_video_binary(
            library=library,
            access_key=access,
            video_id=video_id,
            file_path=video_file,
        ):
            return None

        if chapters_payload:
            self._update_video_metadata(
                library=library,
                access_key=access,
                video_id=video_id,
                chapters=chapters_payload,
            )

        if transcript_file and transcript_file.exists():
            self._upload_transcript_caption(
                library=library,
                access_key=access,
                video_id=video_id,
                transcript_path=transcript_file,
                language=caption_lang,
            )

        logger.info(
            f"Uploaded video '{title}' to Bunny Stream (library={library}, video_id={video_id})."
        )
        return {
            "library_id": library,
            "video_id": video_id,
            "title": title,
        }

    # --------------------------------------------------------------------- #
    # Internal helpers
    # --------------------------------------------------------------------- #

    def _prepare_chapters(
        self,
        chapters: Optional[Sequence[Dict[str, str]]],
    ) -> List[Dict[str, str]]:
        """Load and normalise chapter data for Bunny."""
        if not chapters:
            timestamps_path = self.output_dir / "timestamps.json"
            if timestamps_path.exists():
                try:
                    with open(timestamps_path, "r", encoding="utf-8") as handle:
                        stored = json.load(handle)
                    candidate = stored[0].get("timestamps") if stored else None
                    chapters = candidate if isinstance(candidate, list) else None
                except (json.JSONDecodeError, OSError, AttributeError, IndexError) as exc:
                    logger.warning(f"Unable to load timestamps.json for Bunny chapters: {exc}")
                    chapters = None

        if not chapters:
            return []

        normalised: List[Dict[str, str]] = []
        for entry in chapters:
            title = (entry.get("title") or "").strip()
            start = self._format_chapter_time(entry.get("start"))
            end = self._format_chapter_time(entry.get("end"))
            if not title or start is None or end is None:
                continue
            normalised.append(
                {
                    "title": title,
                    "start": start,
                    "end": end,
                }
            )
        return normalised

    def _resolve_transcript(self, transcript_path: Optional[str]) -> Optional[Path]:
        """Resolve transcript file path, if any is present."""
        if transcript_path:
            candidate = Path(transcript_path)
            return candidate if candidate.exists() else None

        default_path = self.output_dir / "transcript.vtt"
        return default_path if default_path.exists() else None

    def _create_video_entry(
        self,
        *,
        library: str,
        access_key: str,
        title: str,
        collection_id: Optional[str],
    ) -> Optional[Dict[str, str]]:
        """Create a Bunny video record and return the decoded payload."""
        payload: Dict[str, str] = {"title": title}
        if collection_id:
            payload["collectionId"] = collection_id

        url = f"{self._API_BASE}/library/{library}/videos"
        response = self._perform_request(
            method="POST",
            url=url,
            access_key=access_key,
            json=payload,
            timeout=30,
        )
        if not response:
            return None

        try:
            return response.json()
        except json.JSONDecodeError as exc:
            logger.error(f"Failed to decode Bunny create-video response: {exc}")
            return None

    def _upload_video_binary(
        self,
        *,
        library: str,
        access_key: str,
        video_id: str,
        file_path: Path,
    ) -> bool:
        """Stream the MP4 file to Bunny."""
        url = f"{self._API_BASE}/library/{library}/videos/{video_id}"
        headers = {"Content-Type": "application/octet-stream"}

        try:
            with open(file_path, "rb") as file_handle:
                response = self._perform_request(
                    method="PUT",
                    url=url,
                    access_key=access_key,
                    data=file_handle,
                    headers=headers,
                    timeout=600,
                )
        except OSError as exc:
            logger.error(f"Unable to open video file for Bunny upload: {exc}")
            return False

        return response is not None

    def _update_video_metadata(
        self,
        *,
        library: str,
        access_key: str,
        video_id: str,
        chapters: Iterable[Dict[str, str]],
    ) -> None:
        """Update Bunny video metadata with chapter information."""
        url = f"{self._API_BASE}/library/{library}/videos/{video_id}"
        payload = {"chapters": list(chapters)}

        response = self._perform_request(
            method="POST",
            url=url,
            access_key=access_key,
            json=payload,
            timeout=30,
        )
        if response is None:
            logger.warning("Failed to update Bunny chapters; response was empty.")

    def _upload_transcript_caption(
        self,
        *,
        library: str,
        access_key: str,
        video_id: str,
        transcript_path: Path,
        language: str,
    ) -> None:
        """Create or update a caption track with the generated transcript."""
        caption_id = self._ensure_caption_track(
            library=library,
            access_key=access_key,
            video_id=video_id,
            language=language,
        )
        if not caption_id:
            return

        url = f"{self._API_BASE}/library/{library}/videos/{video_id}/captions/{caption_id}"
        files = {"captionsFile": ("transcript.vtt", transcript_path.read_bytes(), "text/vtt")}

        response = self._perform_request(
            method="PUT",
            url=url,
            access_key=access_key,
            files=files,
            timeout=30,
        )
        if response is None:
            logger.warning("Failed to upload transcript captions to Bunny.")

    def _ensure_caption_track(
        self,
        *,
        library: str,
        access_key: str,
        video_id: str,
        language: str,
    ) -> Optional[str]:
        """Ensure a caption slot exists and return its identifier."""
        url = f"{self._API_BASE}/library/{library}/videos/{video_id}/captions"
        payload = {
            "srclang": language,
            "captionTitle": language.upper(),
        }

        response = self._perform_request(
            method="POST",
            url=url,
            access_key=access_key,
            json=payload,
            timeout=15,
            allow_error_statuses={409},
        )

        if response is None:
            return None

        # If the caption already exists, try to parse the identifier from the body.
        try:
            data = response.json()
        except json.JSONDecodeError:
            return None

        caption_id = data.get("guid") or data.get("id")
        if caption_id:
            return str(caption_id)

        # Existing caption conflict responses may include a list of captions.
        if isinstance(data, dict) and "items" in data:
            items = data["items"]
            for item in items:
                if str(item.get("srclang", "")).lower() == language.lower():
                    return str(item.get("guid") or item.get("id") or "")

        return None

    def _perform_request(
        self,
        *,
        method: str,
        url: str,
        access_key: str,
        allow_error_statuses: Optional[Iterable[int]] = None,
        timeout: int,
        **kwargs,
    ) -> Optional[Response]:
        """Wrapper around requests.request with logging and error handling."""
        headers = kwargs.pop("headers", {}) or {}
        headers.setdefault("AccessKey", access_key)

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=headers,
                timeout=timeout,
                **kwargs,
            )
            if allow_error_statuses and response.status_code in allow_error_statuses:
                return response

            response.raise_for_status()
            return response
        except requests.RequestException as exc:
            logger.error(f"Bunny API request failed ({method} {url}): {exc}")
            return None

    def _format_chapter_time(self, raw: Optional[str]) -> Optional[str]:
        """Convert HH:MM:SS timestamps to Bunny's preferred format."""
        if not raw:
            return None

        parts = raw.strip().split(":")
        if len(parts) == 3:
            hours, minutes, seconds = parts
        elif len(parts) == 2:
            hours, minutes, seconds = "0", parts[0], parts[1]
        else:
            return None

        try:
            total_seconds = (
                int(hours) * 3600
                + int(minutes) * 60
                + int(float(seconds))
            )
        except ValueError:
            return None

        if total_seconds >= 3600:
            hrs = total_seconds // 3600
            mins = (total_seconds % 3600) // 60
            secs = total_seconds % 60
            return f"{hrs}:{mins:02d}:{secs:02d}"

        mins = total_seconds // 60
        secs = total_seconds % 60
        return f"{mins}:{secs:02d}"
