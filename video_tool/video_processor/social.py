from __future__ import annotations

import mimetypes
import time
from pathlib import Path
from typing import Dict, List, Optional

import requests

from video_tool.config import get_credential
from .shared import logger

_X_API_BASE = "https://api.x.com/2"
_X_MEDIA_UPLOAD_URL = "https://api.x.com/2/media/upload"
_LINKEDIN_API_BASE = "https://api.linkedin.com/v2"

_X_VIDEO_CATEGORY = "tweet_video"
_X_UPLOAD_CHUNK_SIZE = 4 * 1024 * 1024
_X_UPLOAD_TIMEOUT_SECONDS = 30
_X_UPLOAD_MAX_WAIT_SECONDS = 600


class SocialDeploymentMixin:
    """Handle posting to X and LinkedIn."""

    def _get_x_token(self, access_token: Optional[str]) -> Optional[str]:
        token = (access_token or get_credential("x_bearer_token") or "").strip()
        if not token:
            logger.error("X API bearer token not configured.")
            return None
        return token

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
        access_token: Optional[str] = None,
        video_path: Optional[str] = None,
    ) -> Optional[Dict[str, object]]:
        """Post a thread to X. Returns metadata for created tweets."""
        if not texts:
            logger.error("No text provided for X thread.")
            return None

        token = self._get_x_token(access_token)
        if not token:
            return None

        media_id = None
        if video_path:
            media_id = self._upload_x_media(video_path, token)
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
                headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
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
        video_title: Optional[str] = None,
    ) -> Optional[Dict[str, str]]:
        """Publish a LinkedIn post, optionally with a video upload."""
        token = self._get_linkedin_token(access_token)
        if not token:
            return None

        author = self._get_linkedin_author(author_urn)
        if not author:
            return None

        media_asset = None
        media_title = video_title

        if video_path:
            media_title = media_title or Path(video_path).stem
            upload_result = self._upload_linkedin_video(
                video_path,
                token,
                author,
            )
            if not upload_result:
                return None
            media_asset = upload_result

        post_payload: Dict[str, object] = {
            "author": author,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {"com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"},
        }

        if media_asset:
            post_payload["specificContent"]["com.linkedin.ugc.ShareContent"].update(
                {
                    "shareMediaCategory": "VIDEO",
                    "media": [
                        {
                            "status": "READY",
                            "media": media_asset,
                            "title": {"text": media_title or "Video"},
                        }
                    ],
                }
            )

        response = requests.post(
            f"{_LINKEDIN_API_BASE}/ugcPosts",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-RestLi-Protocol-Version": "2.0.0",
            },
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

    def _upload_x_media(self, video_path: str, token: str) -> Optional[str]:
        file_path = Path(video_path)
        if not file_path.exists():
            logger.error("X media upload failed; file missing: %s", video_path)
            return None

        mime_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        total_bytes = file_path.stat().st_size

        init_response = requests.post(
            _X_MEDIA_UPLOAD_URL,
            headers={"Authorization": f"Bearer {token}"},
            files={
                "command": (None, "INIT"),
                "media_type": (None, mime_type),
                "total_bytes": (None, str(total_bytes)),
                "media_category": (None, _X_VIDEO_CATEGORY),
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
        media_id = _extract_x_media_id(init_data)
        if not media_id:
            logger.error("X media INIT response missing media id: %s", init_response.text)
            return None

        with open(file_path, "rb") as handle:
            segment_index = 0
            while True:
                chunk = handle.read(_X_UPLOAD_CHUNK_SIZE)
                if not chunk:
                    break
                append_response = requests.post(
                    _X_MEDIA_UPLOAD_URL,
                    headers={"Authorization": f"Bearer {token}"},
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

        finalize_response = requests.post(
            f"{_X_MEDIA_UPLOAD_URL}/{media_id}/finalize",
            headers={"Authorization": f"Bearer {token}"},
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
        processing_info = _extract_processing_info(finalize_data)
        if processing_info:
            if not self._wait_for_x_processing(token, media_id, processing_info):
                return None

        return str(media_id)

    def _wait_for_x_processing(self, token: str, media_id: str, info: Dict[str, object]) -> bool:
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
                headers={"Authorization": f"Bearer {token}"},
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
            info = _extract_processing_info(status_data) or {}
            state = str(info.get("state") or "").lower()
            if state == "succeeded":
                return True
            if state == "failed":
                logger.error("X media processing failed: %s", info)
                return False

        logger.error("X media processing timed out after %ss", _X_UPLOAD_MAX_WAIT_SECONDS)
        return False

    def _upload_linkedin_video(self, video_path: str, token: str, author: str) -> Optional[str]:
        file_path = Path(video_path)
        if not file_path.exists():
            logger.error("LinkedIn video upload failed; file missing: %s", video_path)
            return None

        register_payload = {
            "registerUploadRequest": {
                "recipes": ["urn:li:digitalmediaRecipe:feedshare-video"],
                "owner": author,
                "serviceRelationships": [
                    {
                        "relationshipType": "OWNER",
                        "identifier": "urn:li:userGeneratedContent",
                    }
                ],
            }
        }

        register_response = requests.post(
            f"{_LINKEDIN_API_BASE}/assets?action=registerUpload",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "X-RestLi-Protocol-Version": "2.0.0",
            },
            json=register_payload,
            timeout=_X_UPLOAD_TIMEOUT_SECONDS,
        )

        if not register_response.ok:
            logger.error(
                "LinkedIn register upload failed (%s): %s",
                register_response.status_code,
                register_response.text,
            )
            return None

        register_data = _safe_json(register_response)
        upload_info = (
            register_data.get("value", {})
            .get("uploadMechanism", {})
            .get("com.linkedin.digitalmedia.uploading.MediaUploadHttpRequest", {})
        )
        upload_url = upload_info.get("uploadUrl")
        asset_urn = register_data.get("value", {}).get("asset")

        if not upload_url or not asset_urn:
            logger.error("LinkedIn upload registration missing data: %s", register_response.text)
            return None

        mime_type = mimetypes.guess_type(str(file_path))[0] or "application/octet-stream"
        with open(file_path, "rb") as handle:
            upload_response = requests.put(
                upload_url,
                headers={"Content-Type": mime_type},
                data=handle,
                timeout=_X_UPLOAD_TIMEOUT_SECONDS,
            )

        if not upload_response.ok:
            logger.error(
                "LinkedIn binary upload failed (%s): %s",
                upload_response.status_code,
                upload_response.text,
            )
            return None

        return str(asset_urn)


def _safe_json(response: requests.Response) -> Dict[str, object]:
    try:
        return response.json()
    except ValueError:
        return {}


def _extract_x_media_id(payload: Dict[str, object]) -> Optional[str]:
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, dict):
        media_id = data.get("id") or data.get("media_id")
        if media_id:
            return str(media_id)
    media_id = payload.get("media_id_string") if isinstance(payload, dict) else None
    if media_id:
        return str(media_id)
    return None


def _extract_processing_info(payload: Dict[str, object]) -> Optional[Dict[str, object]]:
    if not isinstance(payload, dict):
        return None
    data = payload.get("data") if isinstance(payload, dict) else None
    if isinstance(data, dict) and "processing_info" in data:
        info = data.get("processing_info")
        return info if isinstance(info, dict) else None
    info = payload.get("processing_info")
    if isinstance(info, dict):
        return info
    return None
