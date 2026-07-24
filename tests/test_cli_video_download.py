"""Tests for video download CLI output path handling."""

from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from video_tool.cli import app

runner = CliRunner()


@pytest.mark.unit
def test_video_download_uses_output_path(tmp_path: Path) -> None:
    output_path = tmp_path / "my-video.mp4"

    with patch("video_tool.cli.video_commands.VideoProcessor") as mock_processor:
        result = runner.invoke(
            app,
            ["video", "download", "-u", "https://example.com/video", "-o", str(output_path)],
        )

    assert result.exit_code == 0
    instance = mock_processor.return_value
    args, _ = instance.download_video.call_args
    assert args[0] == "https://example.com/video"
    assert Path(args[1]) == output_path


@pytest.mark.unit
def test_video_download_directory_output_path_uses_title_template(tmp_path: Path) -> None:
    output_dir = tmp_path / "downloads"
    output_dir.mkdir()

    with patch("video_tool.cli.video_commands.VideoProcessor") as mock_processor:
        result = runner.invoke(
            app,
            ["video", "download", "-u", "https://example.com/video", "-o", str(output_dir)],
        )

    assert result.exit_code == 0
    instance = mock_processor.return_value
    args, _ = instance.download_video.call_args
    output_template = Path(args[1])
    assert output_template.parent == output_dir
    assert output_template.name == "%(title)s.%(ext)s"


@pytest.mark.unit
def test_video_download_appends_mp4_suffix_when_missing(tmp_path: Path) -> None:
    output_path = tmp_path / "my-video"
    expected_path = output_path.with_suffix(".mp4")

    with patch("video_tool.cli.video_commands.VideoProcessor") as mock_processor:
        result = runner.invoke(
            app,
            ["video", "download", "-u", "https://example.com/video", "-o", str(output_path)],
        )

    assert result.exit_code == 0
    instance = mock_processor.return_value
    args, _ = instance.download_video.call_args
    assert Path(args[1]) == expected_path
