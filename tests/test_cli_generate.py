"""Tests for the generate command group."""

import pytest
from typer.testing import CliRunner
from unittest.mock import patch

from video_tool.cli import app


runner = CliRunner()


@pytest.mark.unit
def test_generate_group_exists():
    """Verify generate command group is registered."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "generate" in result.stdout


@pytest.mark.unit
def test_generate_help():
    """Verify generate group help shows all commands."""
    result = runner.invoke(app, ["generate", "--help"])
    assert result.exit_code == 0
    assert "AI-powered content generation" in result.stdout
    assert "transcript" in result.stdout
    assert "description" in result.stdout
    assert "context-cards" in result.stdout


@pytest.mark.unit
def test_generate_transcript_help():
    """Verify transcript command help."""
    result = runner.invoke(app, ["generate", "transcript", "--help"])
    assert result.exit_code == 0
    assert "Groq Whisper" in result.stdout
    assert "--input" in result.stdout or "-i" in result.stdout


@pytest.mark.unit
def test_generate_description_help():
    """Verify description command help."""
    result = runner.invoke(app, ["generate", "description", "--help"])
    assert result.exit_code == 0
    assert "--input" in result.stdout or "-i" in result.stdout
    assert "--timestamps" in result.stdout or "-t" in result.stdout


@pytest.mark.unit
def test_generate_context_cards_help():
    """Verify context-cards command help."""
    result = runner.invoke(app, ["generate", "context-cards", "--help"])
    assert result.exit_code == 0
    assert "--input" in result.stdout or "-i" in result.stdout
    assert "--output" in result.stdout or "-o" in result.stdout


@pytest.mark.unit
def test_generate_transcript_requires_groq_key():
    """Verify transcript command checks for Groq API key."""
    with patch("video_tool.cli.get_credential", return_value=None):
        result = runner.invoke(app, ["generate", "transcript", "-i", "test.mp4"])
        assert result.exit_code == 1
        assert "Groq API key" in result.stdout or "groq" in result.stdout.lower()


@pytest.mark.unit
def test_generate_description_requires_openai_key(tmp_path):
    """Verify description command checks for OpenAI API key."""
    # Create a temp VTT file for the test
    test_file = tmp_path / "test.vtt"
    test_file.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nTest transcript")

    with patch("video_tool.cli.generate_commands.ensure_openai_key", return_value=False):
        result = runner.invoke(app, ["generate", "description", "-i", str(test_file)])
        assert result.exit_code == 1


@pytest.mark.unit
def test_generate_context_cards_requires_openai_key(tmp_path):
    """Verify context-cards command checks for OpenAI API key."""
    # Create a temp VTT file for the test
    test_file = tmp_path / "test.vtt"
    test_file.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nTest transcript")

    with patch("video_tool.cli.generate_commands.ensure_openai_key", return_value=False):
        result = runner.invoke(app, ["generate", "context-cards", "-i", str(test_file)])
        assert result.exit_code == 1
