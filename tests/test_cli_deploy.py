"""Tests for upload/deploy CLI commands."""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from video_tool.cli import app


runner = CliRunner()


@pytest.mark.unit
def test_bunny_transcript_uses_stored_language_when_flag_omitted(tmp_path):
    """Omitting --language should fall back to bunny_caption_language credential."""
    transcript = tmp_path / "transcript.vtt"
    transcript.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:01.000\nHello", encoding="utf-8")

    def fake_get_credential(key: str):
        return "es" if key == "bunny_caption_language" else None

    with (
        patch("video_tool.cli.deploy_commands.get_credential", side_effect=fake_get_credential),
        patch("video_tool.cli.deploy_commands.VideoProcessor") as mock_processor_cls,
    ):
        mock_processor = mock_processor_cls.return_value
        mock_processor.update_bunny_transcript.return_value = True

        result = runner.invoke(
            app,
            [
                "upload",
                "bunny-transcript",
                "--video-id",
                "video-123",
                "--transcript-path",
                str(transcript),
                "--bunny-library-id",
                "library-123",
                "--bunny-access-key",
                "access-123",
            ],
        )

    assert result.exit_code == 0
    mock_processor.update_bunny_transcript.assert_called_once()
    assert mock_processor.update_bunny_transcript.call_args.kwargs["language"] == "es"
