"""YouTube deployment mixin for video uploads and metadata management."""

from __future__ import annotations

import datetime as dt
import json
import mimetypes
import os
import re
import stat
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import Resource, build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload
from loguru import logger

# YouTube API scopes
YOUTUBE_SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

# Config directory and files
CONFIG_DIR = Path.home() / ".config" / "video-tool"
CLIENT_SECRETS_PATH = CONFIG_DIR / "client_secrets.json"
CREDENTIALS_PATH = CONFIG_DIR / "youtube_credentials.json"
YOUTUBE_PROFILES_DIR = CONFIG_DIR / "youtube"
ACTIVE_PROFILE_PATH = YOUTUBE_PROFILES_DIR / "active-profile.txt"
DEFAULT_YOUTUBE_PROFILE = "default"
LEGACY_YOUTUBE_PROFILE = "legacy"

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

    @staticmethod
    def _normalize_youtube_profile_name(profile: str | None) -> str:
        value = (profile or DEFAULT_YOUTUBE_PROFILE).strip().lower()
        value = re.sub(r"[^a-z0-9._-]+", "-", value).strip("._-")
        return value or DEFAULT_YOUTUBE_PROFILE

    @classmethod
    def get_effective_youtube_profile(cls, profile: str | None = None) -> str:
        if profile:
            return cls._normalize_youtube_profile_name(profile)

        if ACTIVE_PROFILE_PATH.exists():
            active = ACTIVE_PROFILE_PATH.read_text(encoding="utf-8").strip()
            if active:
                return cls._normalize_youtube_profile_name(active)

        if CREDENTIALS_PATH.exists():
            return LEGACY_YOUTUBE_PROFILE

        return DEFAULT_YOUTUBE_PROFILE

    @classmethod
    def get_youtube_credentials_path(cls, profile: str | None = None) -> Path:
        effective_profile = cls.get_effective_youtube_profile(profile)
        if effective_profile == LEGACY_YOUTUBE_PROFILE:
            return CREDENTIALS_PATH
        return YOUTUBE_PROFILES_DIR / f"{effective_profile}.json"

    @classmethod
    def set_active_youtube_profile(cls, profile: str) -> Path:
        effective_profile = cls._normalize_youtube_profile_name(profile)
        YOUTUBE_PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        ACTIVE_PROFILE_PATH.write_text(f"{effective_profile}\n", encoding="utf-8")
        os.chmod(ACTIVE_PROFILE_PATH, stat.S_IRUSR | stat.S_IWUSR)
        return ACTIVE_PROFILE_PATH

    @staticmethod
    def _read_credentials_file(path: Path) -> dict | None:
        if not path.exists():
            return None
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return None

    @classmethod
    def list_youtube_profiles(cls) -> list[dict[str, str | None]]:
        profiles: list[dict[str, str | None]] = []
        active_profile = cls.get_effective_youtube_profile()

        if YOUTUBE_PROFILES_DIR.exists():
            for path in sorted(YOUTUBE_PROFILES_DIR.glob("*.json")):
                data = cls._read_credentials_file(path) or {}
                name = path.stem
                profiles.append(
                    {
                        "name": name,
                        "path": str(path),
                        "channel_id": data.get("channel_id"),
                        "channel_title": data.get("channel_title"),
                        "is_active": "true" if name == active_profile else "false",
                    }
                )

        if CREDENTIALS_PATH.exists():
            data = cls._read_credentials_file(CREDENTIALS_PATH) or {}
            profiles.append(
                {
                    "name": LEGACY_YOUTUBE_PROFILE,
                    "path": str(CREDENTIALS_PATH),
                    "channel_id": data.get("channel_id"),
                    "channel_title": data.get("channel_title"),
                    "is_active": "true" if active_profile == LEGACY_YOUTUBE_PROFILE else "false",
                }
            )

        return profiles

    @classmethod
    def _fetch_authenticated_channel_info(cls, credentials: Credentials) -> dict[str, str]:
        service = build("youtube", "v3", credentials=credentials)
        response = service.channels().list(part="id,snippet", mine=True).execute()
        items = response.get("items") or []
        if not items:
            return {}
        channel = items[0]
        snippet = channel.get("snippet") or {}
        return {
            "channel_id": channel.get("id", ""),
            "channel_title": snippet.get("title", ""),
        }

    def _get_youtube_service(self, youtube_profile: str | None = None) -> Resource | None:
        """Load credentials and build YouTube API service."""
        credentials_path = self.get_youtube_credentials_path(youtube_profile)
        if not credentials_path.exists():
            logger.error(
                f"YouTube credentials not found for profile '{self.get_effective_youtube_profile(youtube_profile)}'. "
                "Run 'video-tool config youtube-auth' first."
            )
            return None

        try:
            with open(credentials_path, encoding="utf-8") as f:
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
                self._save_youtube_credentials(
                    credentials,
                    creds_data,
                    credentials_path=credentials_path,
                )

            return build("youtube", "v3", credentials=credentials)

        except Exception as e:
            logger.error(f"Failed to initialize YouTube API service: {e}")
            return None

    def _save_youtube_credentials(
        self, credentials: Credentials, existing_data: dict | None = None
        , profile: str | None = None,
        credentials_path: Path | None = None,
    ) -> None:
        """Save credentials to disk."""
        creds_data = existing_data or {}
        target_path = credentials_path or self.get_youtube_credentials_path(profile)
        effective_profile = self.get_effective_youtube_profile(profile)
        creds_data.update({
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
        })
        if effective_profile != LEGACY_YOUTUBE_PROFILE:
            creds_data["profile"] = effective_profile

        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            json.dump(creds_data, f, indent=2)
        # Restrict permissions to owner only (0600)
        os.chmod(target_path, stat.S_IRUSR | stat.S_IWUSR)

    @staticmethod
    def youtube_authenticate(
        client_secrets_path: str | None = None,
        profile: str | None = None,
        set_active: bool = True,
    ) -> bool:
        """Run OAuth2 flow and save credentials.

        Args:
            client_secrets_path: Path to client_secrets.json from Google Cloud Console
            profile: Named YouTube auth profile
            set_active: Whether to mark this profile as the active default

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

            profile_name = YouTubeDeploymentMixin.get_effective_youtube_profile(profile)
            if profile_name == LEGACY_YOUTUBE_PROFILE:
                profile_name = DEFAULT_YOUTUBE_PROFILE
            credentials_path = YouTubeDeploymentMixin.get_youtube_credentials_path(profile_name)
            channel_info = YouTubeDeploymentMixin._fetch_authenticated_channel_info(credentials)

            # Save credentials
            creds_data = {
                "token": credentials.token,
                "refresh_token": credentials.refresh_token,
                "token_uri": credentials.token_uri,
                "client_id": credentials.client_id,
                "client_secret": credentials.client_secret,
                "profile": profile_name,
                "authenticated_at": dt.datetime.now(dt.UTC).isoformat(),
                **channel_info,
            }

            credentials_path.parent.mkdir(parents=True, exist_ok=True)
            with open(credentials_path, "w", encoding="utf-8") as f:
                json.dump(creds_data, f, indent=2)
            # Restrict permissions to owner only (0600)
            os.chmod(credentials_path, stat.S_IRUSR | stat.S_IWUSR)

            if set_active:
                YouTubeDeploymentMixin.set_active_youtube_profile(profile_name)

            logger.info(f"YouTube credentials saved to {credentials_path}")
            return True

        except Exception as e:
            logger.error(f"YouTube authentication failed: {e}")
            return False

    def upload_youtube_video(
        self,
        video_path: str,
        title: str,
        description: str = "",
        tags: list[str] | None = None,
        category_id: int = 27,  # Education
        privacy_status: str = "private",
        thumbnail_path: str | None = None,
        youtube_profile: str | None = None,
    ) -> dict[str, str] | None:
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
        youtube = self._get_youtube_service(youtube_profile)
        if not youtube:
            return None

        video_file = Path(video_path)
        if not video_file.exists():
            logger.error(f"Video file not found: {video_path}")
            return None

        # Validate privacy status - only private/unlisted allowed (public disabled for safety)
        if privacy_status not in ("private", "unlisted"):
            logger.warning(f"Invalid privacy status '{privacy_status}', using 'private'. Public uploads are disabled.")
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
                self.upload_youtube_thumbnail(
                    video_id,
                    thumbnail_path,
                    youtube_profile=youtube_profile,
                )

            return {
                "video_id": video_id,
                "url": f"https://www.youtube.com/watch?v={video_id}",
                "title": title,
                "privacy_status": privacy_status,
                "profile": self.get_effective_youtube_profile(youtube_profile),
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
        title: str | None = None,
        description: str | None = None,
        tags: list[str] | None = None,
        category_id: int | None = None,
        youtube_profile: str | None = None,
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
        youtube = self._get_youtube_service(youtube_profile)
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
        youtube_profile: str | None = None,
    ) -> bool:
        """Upload or update thumbnail for a YouTube video.

        Args:
            video_id: YouTube video ID
            thumbnail_path: Path to thumbnail image (PNG/JPG, max 2MB)

        Returns:
            True if upload succeeded
        """
        youtube = self._get_youtube_service(youtube_profile)
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
        youtube_profile: str | None = None,
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
        youtube = self._get_youtube_service(youtube_profile)
        if not youtube:
            return False

        caption_file = Path(caption_path)
        if not caption_file.exists():
            logger.error(f"Caption file not found: {caption_path}")
            return False

        # Detect MIME type based on extension
        suffix = caption_file.suffix.lower()
        caption_mime_types = {
            ".vtt": "text/vtt",
            ".srt": "application/x-subrip",
            ".sbv": "text/x-youtube-sbv",
            ".sub": "text/x-mpsub",
        }
        mimetype = (
            caption_mime_types.get(suffix)
            or mimetypes.guess_type(str(caption_file))[0]
            or "application/octet-stream"
        )

        try:
            media = MediaFileUpload(str(caption_file), mimetype=mimetype)

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
    def get_youtube_credentials_status() -> dict[str, bool]:
        """Check status of YouTube credentials.

        Returns:
            Dict with 'client_secrets_exists' and 'credentials_exist' flags
        """
        return {
            "client_secrets_exists": CLIENT_SECRETS_PATH.exists(),
            "credentials_exist": bool(YouTubeDeploymentMixin.list_youtube_profiles()),
            "active_profile": YouTubeDeploymentMixin.get_effective_youtube_profile(),
            "profiles": YouTubeDeploymentMixin.list_youtube_profiles(),
        }
