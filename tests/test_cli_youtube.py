"""CLI-level tests for the YouTube upload commands (publish phase)."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from video_tool.cli import app

runner = CliRunner()


# --- youtube-video ---


@pytest.mark.unit
def test_youtube_upload_happy_path(tmp_path: Path) -> None:
    """upload youtube-video uploads privately and records metadata.json."""
    video = tmp_path / "final.mp4"
    video.write_bytes(b"fake")

    with (
        patch("video_tool.cli.deploy_commands._check_youtube_credentials", return_value=True),
        patch("video_tool.cli.deploy_commands.VideoProcessor") as mock_processor,
    ):
        instance = mock_processor.return_value
        instance.upload_youtube_video.return_value = {
            "video_id": "abc123",
            "url": "https://youtu.be/abc123",
            "profile": "default",
        }

        result = runner.invoke(
            app,
            [
                "upload",
                "youtube-video",
                "-i",
                str(video),
                "--title",
                "My Video",
                "--description",
                "desc",
                "--tags",
                "python, tutorial",
            ],
        )

    assert result.exit_code == 0, result.stdout
    instance.upload_youtube_video.assert_called_once_with(
        video_path=str(video),
        title="My Video",
        description="desc",
        tags=["python", "tutorial"],
        category_id=27,
        privacy_status="private",
        thumbnail_path=None,
        youtube_profile=None,
    )

    metadata_path = tmp_path / "output" / "metadata.json"
    metadata = json.loads(metadata_path.read_text())
    assert metadata["youtube_video"]["video_id"] == "abc123"
    assert metadata["youtube_video"]["privacy_status"] == "private"


@pytest.mark.unit
def test_youtube_upload_rejects_public_privacy(tmp_path: Path) -> None:
    """Public uploads are disabled for safety; only private/unlisted pass."""
    video = tmp_path / "final.mp4"
    video.write_bytes(b"fake")

    with patch("video_tool.cli.deploy_commands._check_youtube_credentials", return_value=True):
        result = runner.invoke(
            app,
            ["upload", "youtube-video", "-i", str(video), "--title", "T", "--privacy", "public"],
        )

    assert result.exit_code == 1


@pytest.mark.unit
def test_youtube_upload_without_credentials_exits_1(tmp_path: Path) -> None:
    video = tmp_path / "final.mp4"
    video.write_bytes(b"fake")

    with patch("video_tool.cli.deploy_commands._check_youtube_credentials", return_value=False):
        result = runner.invoke(app, ["upload", "youtube-video", "-i", str(video), "--title", "T"])

    assert result.exit_code == 1


@pytest.mark.unit
def test_youtube_upload_failure_exits_1(tmp_path: Path) -> None:
    video = tmp_path / "final.mp4"
    video.write_bytes(b"fake")

    with (
        patch("video_tool.cli.deploy_commands._check_youtube_credentials", return_value=True),
        patch("video_tool.cli.deploy_commands.VideoProcessor") as mock_processor,
    ):
        mock_processor.return_value.upload_youtube_video.return_value = None
        result = runner.invoke(app, ["upload", "youtube-video", "-i", str(video), "--title", "T"])

    assert result.exit_code == 1


@pytest.mark.unit
def test_youtube_upload_reads_description_and_tags_files(tmp_path: Path) -> None:
    video = tmp_path / "final.mp4"
    video.write_bytes(b"fake")
    description = tmp_path / "description.md"
    description.write_text("file description")
    tags = tmp_path / "tags.txt"
    tags.write_text("alpha\nbeta\n")

    with (
        patch("video_tool.cli.deploy_commands._check_youtube_credentials", return_value=True),
        patch("video_tool.cli.deploy_commands.VideoProcessor") as mock_processor,
    ):
        instance = mock_processor.return_value
        instance.upload_youtube_video.return_value = {"video_id": "x", "url": "u", "profile": "p"}

        result = runner.invoke(
            app,
            [
                "upload",
                "youtube-video",
                "-i",
                str(video),
                "--title",
                "T",
                "--description-file",
                str(description),
                "--tags-file",
                str(tags),
                "--privacy",
                "unlisted",
            ],
        )

    assert result.exit_code == 0, result.stdout
    kwargs = instance.upload_youtube_video.call_args.kwargs
    assert kwargs["description"] == "file description"
    assert kwargs["tags"] == ["alpha", "beta"]
    assert kwargs["privacy_status"] == "unlisted"


# --- youtube-transcript ---


@pytest.mark.unit
def test_youtube_transcript_happy_path(tmp_path: Path) -> None:
    transcript = tmp_path / "transcript.vtt"
    transcript.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nHello")

    with (
        patch("video_tool.cli.deploy_commands._check_youtube_credentials", return_value=True),
        patch("video_tool.cli.deploy_commands.VideoProcessor") as mock_processor,
    ):
        instance = mock_processor.return_value
        instance.upload_youtube_captions.return_value = True

        result = runner.invoke(
            app,
            [
                "upload",
                "youtube-transcript",
                "--video-id",
                "abc123",
                "--transcript-path",
                str(transcript),
            ],
        )

    assert result.exit_code == 0, result.stdout
    instance.upload_youtube_captions.assert_called_once_with(
        video_id="abc123",
        caption_path=str(transcript),
        language="en",
        name="",
        is_draft=False,
        youtube_profile=None,
    )


@pytest.mark.unit
def test_youtube_transcript_missing_file_exits_1(tmp_path: Path) -> None:
    with patch("video_tool.cli.deploy_commands._check_youtube_credentials", return_value=True):
        result = runner.invoke(
            app,
            [
                "upload",
                "youtube-transcript",
                "--video-id",
                "abc123",
                "--transcript-path",
                str(tmp_path / "missing.vtt"),
            ],
        )

    assert result.exit_code == 1


@pytest.mark.unit
def test_youtube_transcript_upload_failure_exits_1(tmp_path: Path) -> None:
    """Caption upload failures must surface as non-zero exits (publish gate)."""
    transcript = tmp_path / "transcript.vtt"
    transcript.write_text("WEBVTT\n")

    with (
        patch("video_tool.cli.deploy_commands._check_youtube_credentials", return_value=True),
        patch("video_tool.cli.deploy_commands.VideoProcessor") as mock_processor,
    ):
        mock_processor.return_value.upload_youtube_captions.return_value = False
        result = runner.invoke(
            app,
            ["upload", "youtube-transcript", "--video-id", "abc123", "-t", str(transcript)],
        )

    assert result.exit_code == 1


# --- youtube-metadata ---


@pytest.mark.unit
def test_youtube_metadata_happy_path() -> None:
    with (
        patch("video_tool.cli.deploy_commands._check_youtube_credentials", return_value=True),
        patch("video_tool.cli.deploy_commands.VideoProcessor") as mock_processor,
    ):
        instance = mock_processor.return_value
        instance.update_youtube_metadata.return_value = True

        result = runner.invoke(
            app,
            [
                "upload",
                "youtube-metadata",
                "--video-id",
                "abc123",
                "--title",
                "New Title",
                "--tags",
                "one, two",
            ],
        )

    assert result.exit_code == 0, result.stdout
    instance.update_youtube_metadata.assert_called_once_with(
        video_id="abc123",
        title="New Title",
        description=None,
        tags=["one", "two"],
        category_id=None,
        youtube_profile=None,
    )


@pytest.mark.unit
def test_youtube_metadata_requires_a_field() -> None:
    with patch("video_tool.cli.deploy_commands._check_youtube_credentials", return_value=True):
        result = runner.invoke(app, ["upload", "youtube-metadata", "--video-id", "abc123"])

    assert result.exit_code == 1


@pytest.mark.unit
def test_youtube_metadata_failure_exits_1() -> None:
    with (
        patch("video_tool.cli.deploy_commands._check_youtube_credentials", return_value=True),
        patch("video_tool.cli.deploy_commands.VideoProcessor") as mock_processor,
    ):
        mock_processor.return_value.update_youtube_metadata.return_value = False
        result = runner.invoke(app, ["upload", "youtube-metadata", "--video-id", "abc123", "--title", "T"])

    assert result.exit_code == 1
