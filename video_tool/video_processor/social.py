from __future__ import annotations

import mimetypes
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests
from requests_oauthlib import OAuth1

from video_tool.config import get_credential
from loguru import logger

_X_API_BASE = "https://api.x.com/2"
_X_MEDIA_UPLOAD_URL = "https://upload.twitter.com/1.1/media/upload.json"
_LINKEDIN_API_BASE = "https://api.linkedin.com"

_X_VIDEO_CATEGORY = "tweet_video"
_X_UPLOAD_CHUNK_SIZE = 4 * 1024 * 1024
_X_UPLOAD_TIMEOUT_SECONDS = 30
_X_UPLOAD_MAX_WAIT_SECONDS = 600


class SocialDeploymentMixin:
    """Handle posting to X and LinkedIn."""

    def _get_x_oauth(self) -> Optional[OAuth1]:
        """Get OAuth1 auth object for X API."""
        api_key = get_credential("x_api_key")
        api_secret = get_credential("x_api_secret")
        access_token = get_credential("x_access_token")
        access_token_secret = get_credential("x_access_token_secret")

        if not all([api_key, api_secret, access_token, access_token_secret]):
            logger.error("X API OAuth credentials not configured. Run 'video-tool config x-auth'.")
            return None

        return OAuth1(
            api_key,
            api_secret,
            access_token,
            access_token_secret,
        )

    def _get_linkedin_token(self, access_token: Optional[str]) -> Optional[str]:
        token = (access_token or get_credential("linkedin_access_token") or "").strip()
        if not token:
            logger.error("LinkedIn access token not configured.")
            return None
        return token

    def _get_linkedin_author(self, author_urn: Optional[str]) -> Optional[str]:
        urn = (author_urn or get_credential("linkedin_author_urn") or "").strip()
        if not urn:
            logger.error("LinkedIn author URN not configured.")
            return None
        return urn

    def post_x_thread(
        self,
        texts: List[str],
        *,
        video_path: Optional[str] = None,
    ) -> Optional[Dict[str, object]]:
        """Post a thread to X. Returns metadata for created tweets."""
        if not texts:
            logger.error("No text provided for X thread.")
            return None

        auth = self._get_x_oauth()
        if not auth:
            return None

        media_id = None
        if video_path:
            media_id = self._upload_x_media(video_path, auth)
            if not media_id:
                return None

        tweet_ids: List[str] = []
        in_reply_to: Optional[str] = None

        for idx, text in enumerate(texts):
            payload: Dict[str, object] = {"text": text}
            if idx == 0 and media_id:
                payload["media"] = {"media_ids": [media_id]}
            if in_reply_to:
                payload["reply"] = {"in_reply_to_tweet_id": in_reply_to}

            response = requests.post(
                f"{_X_API_BASE}/tweets",
                auth=auth,
                headers={"Content-Type": "application/json"},
                json=payload,
                timeout=_X_UPLOAD_TIMEOUT_SECONDS,
            )

            if not response.ok:
                logger.error(
                    "X API tweet creation failed (%s): %s",
                    response.status_code,
                    response.text,
                )
                return None

            data = _safe_json(response).get("data", {})
            tweet_id = str(data.get("id") or "").strip()
            if not tweet_id:
                logger.error("X API response missing tweet id: %s", response.text)
                return None

            tweet_ids.append(tweet_id)
            in_reply_to = tweet_id

        return {
            "tweet_ids": tweet_ids,
            "primary_tweet_id": tweet_ids[0],
            "primary_url": f"https://x.com/i/status/{tweet_ids[0]}",
        }

    def post_linkedin_update(
        self,
        text: str,
        *,
        access_token: Optional[str] = None,
        author_urn: Optional[str] = None,
        video_path: Optional[str] = None,
    ) -> Optional[Dict[str, str]]:
        """Publish a LinkedIn post using the Posts API."""
        token = self._get_linkedin_token(access_token)
        if not token:
            return None

        author = self._get_linkedin_author(author_urn)
        if not author:
            return None

        media_urn = None
        if video_path:
            upload_result = self._upload_linkedin_video(video_path, token, author)
            if not upload_result:
                return None
            media_urn = upload_result

        # Build Posts API payload
        post_payload: Dict[str, object] = {
            "author": author,
            "commentary": text,
            "visibility": "PUBLIC",
            "distribution": {"feedDistribution": "MAIN_FEED"},
            "lifecycleState": "PUBLISHED",
        }

        if media_urn:
            post_payload["content"] = {"media": {"id": media_urn}}

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-RestLi-Protocol-Version": "2.0.0",
            "LinkedIn-Version": "202401",
        }

        response = requests.post(
            f"{_LINKEDIN_API_BASE}/rest/posts",
            headers=headers,
            json=post_payload,
            timeout=_X_UPLOAD_TIMEOUT_SECONDS,
        )

        if not response.ok:
            logger.error(
                "LinkedIn post failed (%s): %s",
                response.status_code,
                response.text,
            )
            return None

        post_urn = response.headers.get("x-restli-id") or response.headers.get("X-RestLi-Id")
        result = {"post_urn": post_urn or ""}
        if post_urn:
            result["post_url"] = f"https://www.linkedin.com/feed/update/{post_urn}"
        return result

    def _upload_x_media(self, video_path: str, auth: OAuth1) -> Optional[str]:
        """Upload media to X using v1.1 chunked upload."""
        file_path = Path(video_path)
        if not file_path.exists():
            logger.error("X media upload failed; file missing: %s", video_path)
            return None

        mime_type = mimetypes.guess_type(str(file_path))[0] or "video/mp4"
        total_bytes = file_path.stat().st_size

        # INIT
        init_response = requests.post(
            _X_MEDIA_UPLOAD_URL,
            auth=auth,
            data={
                "command": "INIT",
                "media_type": mime_type,
                "total_bytes": str(total_bytes),
                "media_category": _X_VIDEO_CATEGORY,
            },
            timeout=_X_UPLOAD_TIMEOUT_SECONDS,
        )

        if not init_response.ok:
            logger.error(
                "X media INIT failed (%s): %s",
                init_response.status_code,
                init_response.text,
            )
            return None

        init_data = _safe_json(init_response)
        media_id = init_data.get("media_id_string")
        if not media_id:
            logger.error("X media INIT response missing media_id_string: %s", init_response.text)
            return None

        # APPEND chunks
        with open(file_path, "rb") as handle:
            segment_index = 0
            while True:
                chunk = handle.read(_X_UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break

                append_response = requests.post(
                    _X_MEDIA_UPLOAD_URL,
                    auth=auth,
                    data={
                        "command": "APPEND",
                        "media_id": media_id,
                        "segment_index": str(segment_index),
                    },
                    files={"media": chunk},
                    timeout=_X_UPLOAD_TIMEOUT_SECONDS,
                )

                if not append_response.ok:
                    logger.error(
                        "X media APPEND failed (%s): %s",
                        append_response.status_code,
                        append_response.text,
                    )
                    return None

                segment_index += 1

        # FINALIZE
        finalize_response = requests.post(
            _X_MEDIA_UPLOAD_URL,
            auth=auth,
            data={"command": "FINALIZE", "media_id": media_id},
            timeout=_X_UPLOAD_TIMEOUT_SECONDS,
        )

        if not finalize_response.ok:
            logger.error(
                "X media FINALIZE failed (%s): %s",
                finalize_response.status_code,
                finalize_response.text,
            )
            return None

        finalize_data = _safe_json(finalize_response)
        processing_info = finalize_data.get("processing_info")
        if processing_info:
            if not self._wait_for_x_processing(auth, media_id, processing_info):
                return None

        return str(media_id)

    def _wait_for_x_processing(self, auth: OAuth1, media_id: str, info: Dict[str, object]) -> bool:
        """Poll X media status until processing completes."""
        start_time = time.monotonic()
        state = str(info.get("state") or "").lower()
        if state == "failed":
            logger.error("X media processing failed: %s", info)
            return False
        if state == "succeeded":
            return True

        while time.monotonic() - start_time < _X_UPLOAD_MAX_WAIT_SECONDS:
            delay = int(info.get("check_after_secs") or 5)
            time.sleep(max(1, delay))

            status_response = requests.get(
                _X_MEDIA_UPLOAD_URL,
                auth=auth,
                params={"command": "STATUS", "media_id": media_id},
                timeout=_X_UPLOAD_TIMEOUT_SECONDS,
            )

            if not status_response.ok:
                logger.error(
                    "X media STATUS failed (%s): %s",
                    status_response.status_code,
                    status_response.text,
                )
                return False

            status_data = _safe_json(status_response)
            info = status_data.get("processing_info") or {}
            state = str(info.get("state") or "").lower()
            if state == "succeeded":
                return True
            if state == "failed":
                logger.error("X media processing failed: %s", info)
                return False

        logger.error("X media processing timed out after %ss", _X_UPLOAD_MAX_WAIT_SECONDS)
        return False

    def _upload_linkedin_video(self, video_path: str, token: str, author: str) -> Optional[str]:
        """Upload video to LinkedIn and return the video URN."""
        file_path = Path(video_path)
        if not file_path.exists():
            logger.error("LinkedIn video upload failed; file missing: %s", video_path)
            return None

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "X-RestLi-Protocol-Version": "2.0.0",
            "LinkedIn-Version": "202401",
        }

        # Register video upload
        register_payload = {
            "initializeUploadRequest": {
                "owner": author,
            }
        }

        register_response = requests.post(
            f"{_LINKEDIN_API_BASE}/rest/videos?action=initializeUpload",
            headers=headers,
            json=register_payload,
            timeout=_X_UPLOAD_TIMEOUT_SECONDS,
        )

        if not register_response.ok:
            logger.error(
                "LinkedIn video init failed (%s): %s",
                register_response.status_code,
                register_response.text,
            )
            return None

        register_data = _safe_json(register_response)
        value = register_data.get("value", {})
        upload_url = value.get("uploadUrl")
        video_urn = value.get("video")

        if not upload_url or not video_urn:
            logger.error("LinkedIn video init missing data: %s", register_response.text)
            return None

        # Upload the video binary
        mime_type = mimetypes.guess_type(str(file_path))[0] or "video/mp4"
        with open(file_path, "rb") as handle:
            upload_response = requests.put(
                upload_url,
                headers={"Content-Type": mime_type},
                data=handle,
                timeout=300,  # Longer timeout for video upload
            )

        if not upload_response.ok:
            logger.error(
                "LinkedIn video upload failed (%s): %s",
                upload_response.status_code,
                upload_response.text,
            )
            return None

        return str(video_urn)


def _safe_json(response: requests.Response) -> Dict[str, object]:
    try:
        return response.json()
    except ValueError:
        return {}
