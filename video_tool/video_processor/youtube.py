"""YouTube deployment mixin for video uploads and metadata management."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build, Resource
from googleapiclient.http import MediaFileUpload
from googleapiclient.errors import HttpError

from .shared import logger

# YouTube API scopes
YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

# Config directory and files
CONFIG_DIR = Path.home() / ".config" / "video-tool"
CLIENT_SECRETS_PATH = CONFIG_DIR / "client_secrets.json"
CREDENTIALS_PATH = CONFIG_DIR / "youtube_credentials.json"

# YouTube category IDs (common ones)
YOUTUBE_CATEGORIES = {
    "film": 1,
    "autos": 2,
    "music": 10,
    "pets": 15,
    "sports": 17,
    "travel": 19,
    "gaming": 20,
    "vlogging": 21,
    "people": 22,
    "comedy": 23,
    "entertainment": 24,
    "news": 25,
    "howto": 26,
    "education": 27,
    "science": 28,
    "nonprofit": 29,
}


class YouTubeDeploymentMixin:
    """Handle YouTube video uploads, metadata, and caption management."""

    def _get_youtube_service(self) -> Optional[Resource]:
        """Load credentials and build YouTube API service."""
        if not CREDENTIALS_PATH.exists():
            logger.error(
                "YouTube credentials not found. Run 'video-tool config youtube-auth' first."
            )
            return None

        try:
            with open(CREDENTIALS_PATH, "r", encoding="utf-8") as f:
                creds_data = json.load(f)

            credentials = Credentials(
                token=creds_data.get("token"),
                refresh_token=creds_data.get("refresh_token"),
                token_uri=creds_data.get("token_uri", "https://oauth2.googleapis.com/token"),
                client_id=creds_data.get("client_id"),
                client_secret=creds_data.get("client_secret"),
                scopes=YOUTUBE_SCOPES,
            )

            # Refresh if expired
            if credentials.expired and credentials.refresh_token:
                from google.auth.transport.requests import Request
                credentials.refresh(Request())
                # Save refreshed credentials
                self._save_youtube_credentials(credentials, creds_data)

            return build("youtube", "v3", credentials=credentials)

        except Exception as e:
            logger.error(f"Failed to initialize YouTube API service: {e}")
            return None

    def _save_youtube_credentials(
        self, credentials: Credentials, existing_data: Optional[Dict] = None
    ) -> None:
        """Save credentials to disk."""
        creds_data = existing_data or {}
        creds_data.update({
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
        })

        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CREDENTIALS_PATH, "w", encoding="utf-8") as f:
            json.dump(creds_data, f, indent=2)

    @staticmethod
    def youtube_authenticate(client_secrets_path: Optional[str] = None) -> bool:
        """Run OAuth2 flow and save credentials.

        Args:
            client_secrets_path: Path to client_secrets.json from Google Cloud Console

        Returns:
            True if authentication succeeded
        """
        secrets_path = Path(client_secrets_path) if client_secrets_path else CLIENT_SECRETS_PATH

        if not secrets_path.exists():
            logger.error(
                f"Client secrets file not found: {secrets_path}\n"
                "Download from Google Cloud Console and provide path."
            )
            return False

        try:
            # Copy secrets to config dir if from different location
            if secrets_path != CLIENT_SECRETS_PATH:
                CONFIG_DIR.mkdir(parents=True, exist_ok=True)
                import shutil
                shutil.copy(secrets_path, CLIENT_SECRETS_PATH)
                logger.info(f"Copied client secrets to {CLIENT_SECRETS_PATH}")

            flow = InstalledAppFlow.from_client_secrets_file(
                str(CLIENT_SECRETS_PATH), YOUTUBE_SCOPES
            )

            # Run local server for OAuth
            credentials = flow.run_local_server(
                port=8080,
                prompt="consent",
                success_message="Authentication successful! You can close this window.",
            )

            # Save credentials
            creds_data = {
                "token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_uri": credentials.token_uri,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
            }

            with open(CREDENTIALS_PATH, "w", encoding="utf-8") as f:
                json.dump(creds_data, f, indent=2)

            logger.info(f"YouTube credentials saved to {CREDENTIALS_PATH}")
            return True

        except Exception as e:
            logger.error(f"YouTube authentication failed: {e}")
            return False

    def upload_youtube_video(
        self,
        video_path: str,
        title: str,
        description: str = "",
        tags: Optional[List[str]] = None,
        category_id: int = 27,  # Education
        privacy_status: str = "private",
        thumbnail_path: Optional[str] = None,
    ) -> Optional[Dict[str, str]]:
        """Upload a video to YouTube.

        Args:
            video_path: Path to video file
            title: Video title
            description: Video description (can include timestamps for chapters)
            tags: List of tags
            category_id: YouTube category ID (default 27 = Education)
            privacy_status: One of 'private', 'unlisted', 'public'
            thumbnail_path: Optional path to thumbnail image

        Returns:
            Dict with video_id and url, or None on failure
        """
        youtube = self._get_youtube_service()
        if not youtube:
            return None

        video_file = Path(video_path)
        if not video_file.exists():
            logger.error(f"Video file not found: {video_path}")
            return None

        # Validate privacy status
        if privacy_status not in ("private", "unlisted", "public"):
            logger.warning(f"Invalid privacy status '{privacy_status}', using 'private'")
            privacy_status = "private"

        body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": tags or [],
                "categoryId": str(category_id),
            },
            "status": {
                "privacyStatus": privacy_status,
                "selfDeclaredMadeForKids": False,
            },
        }

        try:
            # Use resumable upload for large files
            media = MediaFileUpload(
                str(video_file),
                mimetype="video/*",
                resumable=True,
                chunksize=50 * 1024 * 1024,  # 50MB chunks
            )

            request = youtube.videos().insert(
                part="snippet,status",
                body=body,
                media_body=media,
            )

            logger.info(f"Uploading video: {title}")
            response = None
            while response is None:
                status, response = request.next_chunk()
                if status:
                    progress = int(status.progress() * 100)
                    logger.info(f"Upload progress: {progress}%")

            video_id = response.get("id")
            if not video_id:
                logger.error("Upload succeeded but no video ID returned")
                return None

            logger.info(f"Video uploaded successfully: {video_id}")

            # Upload thumbnail if provided
            if thumbnail_path:
                self.upload_youtube_thumbnail(video_id, thumbnail_path)

            return {
                "video_id": video_id,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "title": title,
                "privacy_status": privacy_status,
            }

        except HttpError as e:
            logger.error(f"YouTube API error during upload: {e}")
            return None
        except Exception as e:
            logger.error(f"Failed to upload video: {e}")
            return None

    def update_youtube_metadata(
        self,
        video_id: str,
        title: Optional[str] = None,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        category_id: Optional[int] = None,
    ) -> bool:
        """Update metadata for an existing YouTube video.

        Args:
            video_id: YouTube video ID
            title: New title (optional)
            description: New description (optional)
            tags: New tags (optional)
            category_id: New category ID (optional)

        Returns:
            True if update succeeded
        """
        youtube = self._get_youtube_service()
        if not youtube:
            return False

        try:
            # First get current video data
            video_response = youtube.videos().list(
                part="snippet",
                id=video_id,
            ).execute()

            if not video_response.get("items"):
                logger.error(f"Video not found: {video_id}")
                return False

            snippet = video_response["items"][0]["snippet"]

            # Update only provided fields
            if title is not None:
                snippet["title"] = title
            if description is not None:
                snippet["description"] = description
            if tags is not None:
                snippet["tags"] = tags
            if category_id is not None:
                snippet["categoryId"] = str(category_id)

            # Update video
            youtube.videos().update(
                part="snippet",
                body={
                    "id": video_id,
                    "snippet": snippet,
                },
            ).execute()

            logger.info(f"Updated metadata for video: {video_id}")
            return True

        except HttpError as e:
            logger.error(f"YouTube API error during metadata update: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to update video metadata: {e}")
            return False

    def upload_youtube_thumbnail(
        self,
        video_id: str,
        thumbnail_path: str,
    ) -> bool:
        """Upload or update thumbnail for a YouTube video.

        Args:
            video_id: YouTube video ID
            thumbnail_path: Path to thumbnail image (PNG/JPG, max 2MB)

        Returns:
            True if upload succeeded
        """
        youtube = self._get_youtube_service()
        if not youtube:
            return False

        thumb_file = Path(thumbnail_path)
        if not thumb_file.exists():
            logger.error(f"Thumbnail file not found: {thumbnail_path}")
            return False

        # Check file size (2MB limit)
        if thumb_file.stat().st_size > 2 * 1024 * 1024:
            logger.error("Thumbnail file exceeds 2MB limit")
            return False

        try:
            media = MediaFileUpload(str(thumb_file), mimetype="image/*")

            youtube.thumbnails().set(
                videoId=video_id,
                media_body=media,
            ).execute()

            logger.info(f"Uploaded thumbnail for video: {video_id}")
            return True

        except HttpError as e:
            logger.error(f"YouTube API error during thumbnail upload: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to upload thumbnail: {e}")
            return False

    def upload_youtube_captions(
        self,
        video_id: str,
        caption_path: str,
        language: str = "en",
        name: str = "",
        is_draft: bool = False,
    ) -> bool:
        """Upload caption track to a YouTube video.

        Args:
            video_id: YouTube video ID
            caption_path: Path to caption file (.vtt, .srt, etc.)
            language: Caption language code (default 'en')
            name: Caption track name (optional)
            is_draft: If True, caption is draft and not visible

        Returns:
            True if upload succeeded
        """
        youtube = self._get_youtube_service()
        if not youtube:
            return False

        caption_file = Path(caption_path)
        if not caption_file.exists():
            logger.error(f"Caption file not found: {caption_path}")
            return False

        try:
            media = MediaFileUpload(str(caption_file), mimetype="text/vtt")

            body = {
                "snippet": {
                    "videoId": video_id,
                    "language": language,
                    "name": name or f"{language.upper()} Captions",
                    "isDraft": is_draft,
                },
            }

            youtube.captions().insert(
                part="snippet",
                body=body,
                media_body=media,
            ).execute()

            logger.info(f"Uploaded captions ({language}) for video: {video_id}")
            return True

        except HttpError as e:
            logger.error(f"YouTube API error during caption upload: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to upload captions: {e}")
            return False

    @staticmethod
    def get_youtube_credentials_status() -> Dict[str, bool]:
        """Check status of YouTube credentials.

        Returns:
            Dict with 'client_secrets_exists' and 'credentials_exist' flags
        """
        return {
            "client_secrets_exists": CLIENT_SECRETS_PATH.exists(),
            "credentials_exist": CREDENTIALS_PATH.exists(),
        }
