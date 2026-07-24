"""Unit tests for deployment credential resolution.

On master, BunnyDeploymentMixin uses os.getenv() for credential fallback.
After the PR merge (refactor/project-audit-fixes), it switches to get_credential().
These tests mock get_credential at the correct module level for both branches.
"""

from unittest.mock import MagicMock, patch

import pytest


def _make_response(json_payload=None, status=200):
    response = MagicMock()
    response.status_code = status
    response.raise_for_status = MagicMock()
    if json_payload is None:
        response.json.side_effect = ValueError("No JSON")
    else:
        response.json.return_value = json_payload
    response.text = ""
    return response


class TestBunnyCredentialResolution:
    """Test credential resolution in BunnyDeploymentMixin."""

    @pytest.fixture
    def mock_processor(self, tmp_path):
        with patch("video_tool.video_processor.base.OpenAI"), \
             patch("video_tool.video_processor.base.Groq"), \
             patch("video_tool.config.get_credential", return_value="test-key"):
            from video_tool.video_processor import VideoProcessor
            return VideoProcessor(str(tmp_path))

    def test_resolve_library_and_access_with_explicit_args(self, mock_processor) -> None:
        """Explicit library_id and access_key should be used directly."""
        result = mock_processor._resolve_library_and_access(
            library_id="lib-1", access_key="access-1"
        )
        assert result == ("lib-1", "access-1")

    def test_resolve_library_and_access_uses_get_credential(
        self, mock_processor, monkeypatch
    ) -> None:
        """When explicit args are None, get_credential provides values."""
        monkeypatch.delenv("BUNNY_LIBRARY_ID", raising=False)
        monkeypatch.delenv("BUNNY_ACCESS_KEY", raising=False)
        with patch("video_tool.video_processor.deployment.get_credential") as mock_cred:
            mock_cred.side_effect = lambda key: {
                "bunny_library_id": "cred-lib",
                "bunny_access_key": "cred-access",
            }.get(key)
            result = mock_processor._resolve_library_and_access(
                library_id=None, access_key=None
            )
        assert result == ("cred-lib", "cred-access")

    def test_resolve_library_and_access_explicit_overrides_credential(
        self, mock_processor, monkeypatch
    ) -> None:
        """Explicit args should work even when get_credential returns values."""
        monkeypatch.setenv("BUNNY_LIBRARY_ID", "env-lib")
        monkeypatch.setenv("BUNNY_ACCESS_KEY", "env-access")
        result = mock_processor._resolve_library_and_access(
            library_id="explicit-lib", access_key="explicit-access"
        )
        assert result == ("explicit-lib", "explicit-access")

    def test_resolve_library_and_access_returns_none_on_missing(
        self, mock_processor, monkeypatch
    ) -> None:
        """Should return None when no credentials are available from any source."""
        monkeypatch.delenv("BUNNY_LIBRARY_ID", raising=False)
        monkeypatch.delenv("BUNNY_ACCESS_KEY", raising=False)
        with patch("video_tool.video_processor.deployment.get_credential", return_value=None):
            result = mock_processor._resolve_library_and_access(
                library_id=None, access_key=None
            )
        assert result is None

    def test_format_chapter_time(self, mock_processor) -> None:
        """Test _format_chapter_time with various formats."""
        assert mock_processor._format_chapter_time("00:01:30") == 90
        assert mock_processor._format_chapter_time("01:30") == 90
        assert mock_processor._format_chapter_time("90") == 90
        assert mock_processor._format_chapter_time(None) is None
        assert mock_processor._format_chapter_time("invalid") is None
        assert mock_processor._format_chapter_time(60) == 60

    def test_format_chapter_time_negative(self, mock_processor) -> None:
        """Negative timestamps should return None."""
        assert mock_processor._format_chapter_time(-1) is None
        assert mock_processor._format_chapter_time("-5") is None

    def test_prepare_chapters_normalizes(self, mock_processor) -> None:
        """_prepare_chapters should normalize and sort chapter data."""
        chapters = [
            {"title": "Second", "start": "00:02:00", "end": "00:03:00"},
            {"title": "First", "start": "00:00:00", "end": "00:01:00"},
        ]
        result = mock_processor._prepare_chapters(chapters)
        assert len(result) == 2
        assert result[0]["start"] == 0
        assert result[0]["title"] == "First"
        assert result[1]["start"] == 120

    def test_prepare_chapters_skips_invalid(self, mock_processor) -> None:
        """_prepare_chapters should skip chapters with missing data."""
        chapters = [
            {"title": "", "start": "00:00:00", "end": "00:01:00"},
            {"title": "Valid", "start": "00:01:00", "end": "00:02:00"},
        ]
        result = mock_processor._prepare_chapters(chapters)
        assert len(result) == 1
        assert result[0]["title"] == "Valid"

    def test_prepare_chapters_empty_input(self, mock_processor) -> None:
        """_prepare_chapters should return empty list for None/empty input."""
        assert mock_processor._prepare_chapters(None) == []
        assert mock_processor._prepare_chapters([]) == []


class TestBunnyVideoOperations:
    """Test video upload and metadata operations."""

    @pytest.fixture
    def mock_processor(self, tmp_path):
        with patch("video_tool.video_processor.base.OpenAI"), \
             patch("video_tool.video_processor.base.Groq"), \
             patch("video_tool.config.get_credential", return_value="test-key"):
            from video_tool.video_processor import VideoProcessor
            return VideoProcessor(str(tmp_path))

    def test_upload_bunny_video_missing_file(self, mock_processor) -> None:
        """upload_bunny_video should return None for missing video file."""
        result = mock_processor.upload_bunny_video(
            video_path="/nonexistent/video.mp4",
            library_id="lib-1",
            access_key="access-1",
        )
        assert result is None

    def test_deploy_to_bunny_requires_credentials(
        self, mock_processor, tmp_path, monkeypatch
    ) -> None:
        """Missing credentials should cause the deployment to return None."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        video_path = output_dir / "final.mp4"
        video_path.write_bytes(b"\x00\x00test")

        monkeypatch.delenv("BUNNY_LIBRARY_ID", raising=False)
        monkeypatch.delenv("BUNNY_ACCESS_KEY", raising=False)
        with patch("video_tool.video_processor.deployment.get_credential", return_value=None):
            result = mock_processor.deploy_to_bunny(
                str(video_path),
                upload_video=True,
                upload_chapters=False,
                upload_transcript=False,
            )
        assert result is None

    def test_upload_bunny_video_success(self, mock_processor, tmp_path) -> None:
        """Full video upload flow should return expected payload."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        video_path = output_dir / "final.mp4"
        video_path.write_bytes(b"\x00fakevideo")

        responses = [
            _make_response({"videoId": "vid-123"}),
            _make_response({}),
        ]

        with patch("video_tool.video_processor.deployment.requests.request", side_effect=responses):
            result = mock_processor.upload_bunny_video(
                video_path=str(video_path),
                library_id="lib-1",
                access_key="access-1",
                collection_id="collection-9",
                video_title="Demo Video",
            )

        assert result == {
            "library_id": "lib-1",
            "video_id": "vid-123",
            "title": "Demo Video",
        }
