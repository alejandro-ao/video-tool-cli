"""Tests for the generate command group."""

import json
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

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


@pytest.mark.unit
def test_generate_transcript_happy_path(tmp_path):
    """generate transcript transcribes media and records metadata.json."""
    video = tmp_path / "final-base.mp4"
    video.write_bytes(b"fake")
    output = tmp_path / "transcript.vtt"

    with patch("video_tool.cli.generate_commands.ensure_groq_key", return_value=True), patch(
        "video_tool.cli.generate_commands.VideoProcessor"
    ) as mock_processor:
        instance = mock_processor.return_value

        def fake_transcript(video_path, output_path):
            # The real processor writes the VTT file it returns
            with open(output_path, "w", encoding="utf-8") as f:
                f.write("WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nHello")
            return output_path

        instance.generate_transcript.side_effect = fake_transcript

        result = runner.invoke(
            app, ["generate", "transcript", "-i", str(video), "-o", str(output)]
        )

    assert result.exit_code == 0, result.stdout
    instance.generate_transcript.assert_called_once_with(
        video_path=str(video), output_path=str(output)
    )

    metadata = json.loads((tmp_path / "metadata.json").read_text())
    assert metadata["transcript_format"] == "vtt"
    assert "Hello" in metadata["transcript"]


@pytest.mark.unit
def test_generate_transcript_rejects_unsupported_format(tmp_path):
    weird = tmp_path / "notes.txt"
    weird.write_text("not media")

    with patch("video_tool.cli.generate_commands.ensure_groq_key", return_value=True):
        result = runner.invoke(app, ["generate", "transcript", "-i", str(weird)])

    assert result.exit_code == 1


@pytest.mark.unit
def test_generate_description_from_vtt_happy_path(tmp_path):
    """generate description with a VTT input skips transcription."""
    transcript = tmp_path / "transcript.vtt"
    transcript.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nHello")
    output = tmp_path / "description.md"

    with patch("video_tool.cli.generate_commands.ensure_config"), patch(
        "video_tool.cli.generate_commands.ensure_openai_key", return_value=True
    ), patch("video_tool.cli.generate_commands.VideoProcessor") as mock_processor:
        instance = mock_processor.return_value
        instance.generate_description.return_value = str(output)

        result = runner.invoke(
            app, ["generate", "description", "-i", str(transcript), "-o", str(output)]
        )

    assert result.exit_code == 0, result.stdout
    instance.generate_transcript.assert_not_called()
    kwargs = instance.generate_description.call_args.kwargs
    assert kwargs["transcript_path"] == str(transcript)
    assert kwargs["output_path"] == str(output)


@pytest.mark.unit
def test_generate_description_from_video_transcribes_first(tmp_path):
    """generate description with a media input transcribes before generating."""
    video = tmp_path / "final-base.mp4"
    video.write_bytes(b"fake")
    output = tmp_path / "description.md"

    with patch("video_tool.cli.generate_commands.ensure_config"), patch(
        "video_tool.cli.generate_commands.ensure_openai_key", return_value=True
    ), patch(
        "video_tool.cli.generate_commands.ensure_groq_key", return_value=True
    ), patch("video_tool.cli.generate_commands.VideoProcessor") as mock_processor:
        instance = mock_processor.return_value
        transcript_path = str(tmp_path / "transcript.vtt")
        instance.generate_transcript.return_value = transcript_path
        instance.generate_description.return_value = str(output)

        result = runner.invoke(
            app, ["generate", "description", "-i", str(video), "-o", str(output)]
        )

    assert result.exit_code == 0, result.stdout
    instance.generate_transcript.assert_called_once()
    kwargs = instance.generate_description.call_args.kwargs
    assert kwargs["transcript_path"] == transcript_path


@pytest.mark.unit
def test_generate_description_rejects_unsupported_input(tmp_path):
    weird = tmp_path / "data.json"
    weird.write_text("{}")

    with patch("video_tool.cli.generate_commands.ensure_config"):
        result = runner.invoke(app, ["generate", "description", "-i", str(weird)])

    assert result.exit_code == 1
