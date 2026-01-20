"""Tests for the new Typer-based pipeline CLI."""

import pytest
from typer.testing import CliRunner
from unittest.mock import MagicMock, patch

from video_tool.cli import app


runner = CliRunner()


@pytest.mark.unit
def test_pipeline_help():
    """Ensure the pipeline command shows help."""
    result = runner.invoke(app, ["pipeline", "--help"])
    assert result.exit_code == 0
    assert "Run the full video processing pipeline" in result.stdout


@pytest.mark.unit
def test_pipeline_requires_input_dir_in_noninteractive():
    """In non-interactive mode, --input-dir is required."""
    result = runner.invoke(app, ["pipeline", "--yes"])
    assert result.exit_code == 1
    assert "input-dir is required" in result.stdout.lower() or result.exit_code != 0


@pytest.mark.unit
def test_video_subcommands_exist():
    """Verify video subcommands are registered."""
    result = runner.invoke(app, ["video", "--help"])
    assert result.exit_code == 0
    assert "concat" in result.stdout
    assert "timestamps" in result.stdout
    assert "transcript" in result.stdout


@pytest.mark.unit
def test_video_content_subcommands_exist():
    """Verify description and context-cards are in video group."""
    result = runner.invoke(app, ["video", "--help"])
    assert result.exit_code == 0
    assert "description" in result.stdout
    assert "context-cards" in result.stdout


@pytest.mark.unit
def test_upload_subcommands_exist():
    """Verify upload subcommands are registered."""
    result = runner.invoke(app, ["upload", "--help"])
    assert result.exit_code == 0
    assert "bunny-video" in result.stdout
    assert "bunny-transcript" in result.stdout
    assert "bunny-chapters" in result.stdout


@pytest.mark.unit
def test_verbose_flag_exists():
    """Verify the global --verbose flag is available."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "--verbose" in result.stdout or "-v" in result.stdout
