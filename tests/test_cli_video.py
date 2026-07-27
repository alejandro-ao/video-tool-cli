"""CLI-level tests for the video commands used by the release workflow.

Covers the canonical produce path: concat -> timestamps (clips mode)
-> extract-audio, plus silence-removal and cut (QC phase).
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from video_tool.cli import app

runner = CliRunner()


# --- concat ---


@pytest.mark.unit
def test_concat_happy_path_fast_mode(tmp_path: Path) -> None:
    """video concat --fast-concat calls the processor and writes metadata."""
    clips = tmp_path / "clips"
    clips.mkdir()
    output = tmp_path / "output" / "final.mp4"

    with patch("video_tool.cli.video_commands.VideoProcessor") as mock_processor:
        instance = mock_processor.return_value
        instance.concatenate_videos.return_value = str(output)
        instance.get_video_metadata.return_value = (None, None, None)

        result = runner.invoke(
            app,
            ["video", "concat", "-i", str(clips), "-o", str(output), "--fast-concat"],
        )

    assert result.exit_code == 0, result.stdout
    mock_processor.assert_called_once_with(str(clips), video_title="final", output_dir=str(output.parent))
    instance.concatenate_videos.assert_called_once_with(skip_reprocessing=True, output_path=str(output))

    metadata = json.loads((output.parent / "metadata.json").read_text())
    assert metadata["output_filename"] == "final.mp4"
    assert metadata["concat_mode"] == "fast"


@pytest.mark.unit
def test_concat_standard_mode_and_relative_output(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Relative --output-path resolves from the current working directory."""
    clips = tmp_path / "clips"
    clips.mkdir()
    working_dir = tmp_path / "working"
    working_dir.mkdir()
    monkeypatch.chdir(working_dir)

    with patch("video_tool.cli.video_commands.VideoProcessor") as mock_processor:
        instance = mock_processor.return_value
        instance.concatenate_videos.return_value = "output/out.mp4"
        instance.get_video_metadata.return_value = (None, None, None)

        result = runner.invoke(
            app,
            ["video", "concat", "-i", str(clips), "-o", "output/out.mp4", "--no-fast-concat"],
        )

    assert result.exit_code == 0, result.stdout
    instance.concatenate_videos.assert_called_once_with(skip_reprocessing=False, output_path="output/out.mp4")
    assert (working_dir / "output").is_dir()


@pytest.mark.unit
def test_concat_invalid_directory_exits_1(tmp_path: Path) -> None:
    result = runner.invoke(app, ["video", "concat", "-i", str(tmp_path / "missing"), "--fast-concat"])
    assert result.exit_code == 1


@pytest.mark.unit
def test_concat_empty_result_exits_1(tmp_path: Path) -> None:
    clips = tmp_path / "clips"
    clips.mkdir()

    with patch("video_tool.cli.video_commands.VideoProcessor") as mock_processor:
        mock_processor.return_value.concatenate_videos.return_value = None
        result = runner.invoke(app, ["video", "concat", "-i", str(clips), "--fast-concat"])

    assert result.exit_code == 1


# --- timestamps ---


@pytest.mark.unit
def test_timestamps_clips_mode_happy_path(tmp_path: Path) -> None:
    """video timestamps --mode clips mirrors the produce-phase1 invocation."""
    clips = tmp_path / "clips"
    clips.mkdir()
    output = tmp_path / "output" / "timestamps.json"

    with patch("video_tool.cli.video_commands.VideoProcessor") as mock_processor:
        instance = mock_processor.return_value
        instance.generate_timestamps.return_value = {"timestamps": [{"start": "0:00", "end": "1:00", "title": "Intro"}]}

        result = runner.invoke(
            app,
            ["video", "timestamps", "--mode", "clips", "-i", str(clips), "-o", str(output)],
        )

    assert result.exit_code == 0, result.stdout
    instance.generate_timestamps.assert_called_once_with(
        output_path=str(output),
        transcript_path=None,
        stamps_from_transcript=False,
        granularity="medium",
        timestamp_notes=None,
    )

    metadata = json.loads((output.parent / "metadata.json").read_text())
    assert metadata["timestamps"][0]["title"] == "Intro"


@pytest.mark.unit
def test_timestamps_transcript_mode_happy_path(tmp_path: Path) -> None:
    """Transcript mode requires the OpenAI key and forwards granularity/notes."""
    transcript = tmp_path / "transcript.vtt"
    transcript.write_text("WEBVTT\n\n00:00:00.000 --> 00:00:05.000\nHello")
    output = tmp_path / "timestamps.json"

    with (
        patch("video_tool.cli.video_commands.ensure_openai_key", return_value=True),
        patch("video_tool.cli.video_commands.VideoProcessor") as mock_processor,
    ):
        instance = mock_processor.return_value
        instance.generate_timestamps.return_value = {"timestamps": []}

        result = runner.invoke(
            app,
            [
                "video",
                "timestamps",
                "--mode",
                "transcript",
                "-i",
                str(transcript),
                "-o",
                str(output),
                "-g",
                "high",
                "-n",
                "keep it short",
            ],
        )

    assert result.exit_code == 0, result.stdout
    instance.generate_timestamps.assert_called_once_with(
        output_path=str(output),
        transcript_path=str(transcript),
        stamps_from_transcript=True,
        granularity="high",
        timestamp_notes="keep it short",
    )


@pytest.mark.unit
def test_timestamps_invalid_mode_exits_1(tmp_path: Path) -> None:
    result = runner.invoke(app, ["video", "timestamps", "--mode", "bogus", "-i", str(tmp_path)])
    assert result.exit_code == 1


@pytest.mark.unit
def test_timestamps_clips_invalid_directory_exits_1(tmp_path: Path) -> None:
    result = runner.invoke(app, ["video", "timestamps", "--mode", "clips", "-i", str(tmp_path / "missing")])
    assert result.exit_code == 1


@pytest.mark.unit
def test_timestamps_transcript_requires_openai_key(tmp_path: Path) -> None:
    transcript = tmp_path / "transcript.vtt"
    transcript.write_text("WEBVTT\n")

    with patch("video_tool.cli.video_commands.ensure_openai_key", return_value=False):
        result = runner.invoke(app, ["video", "timestamps", "--mode", "transcript", "-i", str(transcript)])
    assert result.exit_code == 1


# --- extract-audio ---


@pytest.mark.unit
def test_extract_audio_happy_path(tmp_path: Path) -> None:
    """video extract-audio writes an MP3 via moviepy."""
    video = tmp_path / "final.mp4"
    video.write_bytes(b"fake")
    output = tmp_path / "audio.mp3"

    with patch("moviepy.video.io.VideoFileClip.VideoFileClip") as mock_clip_cls:
        clip = mock_clip_cls.return_value.__enter__.return_value
        clip.audio = MagicMock()

        result = runner.invoke(app, ["video", "extract-audio", "-i", str(video), "-o", str(output)])

    assert result.exit_code == 0, result.stdout
    mock_clip_cls.assert_called_once_with(str(video))
    clip.audio.write_audiofile.assert_called_once_with(str(output), logger=None)


@pytest.mark.unit
def test_extract_audio_defaults_to_stem_mp3(tmp_path: Path) -> None:
    video = tmp_path / "final.mp4"
    video.write_bytes(b"fake")

    with patch("moviepy.video.io.VideoFileClip.VideoFileClip") as mock_clip_cls:
        clip = mock_clip_cls.return_value.__enter__.return_value
        clip.audio = MagicMock()

        # Empty input at the output-path prompt accepts the default
        result = runner.invoke(app, ["video", "extract-audio", "-i", str(video)], input="\n")

    assert result.exit_code == 0, result.stdout
    clip.audio.write_audiofile.assert_called_once_with(str(tmp_path / "final.mp3"), logger=None)


@pytest.mark.unit
def test_extract_audio_no_audio_track_exits_1(tmp_path: Path) -> None:
    video = tmp_path / "silent.mp4"
    video.write_bytes(b"fake")

    with patch("moviepy.video.io.VideoFileClip.VideoFileClip") as mock_clip_cls:
        clip = mock_clip_cls.return_value.__enter__.return_value
        clip.audio = None

        result = runner.invoke(app, ["video", "extract-audio", "-i", str(video)])

    assert result.exit_code == 1


@pytest.mark.unit
def test_extract_audio_invalid_input_exits_1(tmp_path: Path) -> None:
    result = runner.invoke(app, ["video", "extract-audio", "-i", str(tmp_path / "missing.mp4")])
    assert result.exit_code == 1


# --- silence-removal ---


@pytest.mark.unit
def test_silence_removal_happy_path(tmp_path: Path) -> None:
    video = tmp_path / "raw.mp4"
    video.write_bytes(b"fake")
    output = tmp_path / "raw_no_silence.mp4"

    with patch("video_tool.cli.video_commands.VideoProcessor") as mock_processor:
        instance = mock_processor.return_value
        instance.remove_silence_from_video.return_value = str(output)

        result = runner.invoke(
            app,
            ["video", "silence-removal", "-i", str(video), "-o", str(output), "-t", "2.0"],
        )

    assert result.exit_code == 0, result.stdout
    instance.remove_silence_from_video.assert_called_once_with(
        video_path=str(video),
        output_path=str(output),
        min_silence_len=2000,
    )


@pytest.mark.unit
def test_silence_removal_invalid_input_exits_1(tmp_path: Path) -> None:
    result = runner.invoke(app, ["video", "silence-removal", "-i", str(tmp_path / "missing.mp4")])
    assert result.exit_code == 1


# --- cut ---


@pytest.mark.unit
def test_cut_happy_path(tmp_path: Path) -> None:
    """video cut forwards the removal range to the processor (QC phase)."""
    video = tmp_path / "final-base.mp4"
    video.write_bytes(b"fake")
    output = tmp_path / "final-base-cut.mp4"

    with patch("video_tool.cli.video_commands.VideoProcessor") as mock_processor:
        instance = mock_processor.return_value
        instance.cut_video.return_value = str(output)

        result = runner.invoke(
            app,
            ["video", "cut", "-i", str(video), "-o", str(output), "-f", "00:01:00", "-t", "00:02:00"],
        )

    assert result.exit_code == 0, result.stdout
    instance.cut_video.assert_called_once_with(
        str(video), str(output), cut_from="00:01:00", cut_to="00:02:00", gpu=False
    )


@pytest.mark.unit
def test_cut_processor_failure_exits_1(tmp_path: Path) -> None:
    video = tmp_path / "final.mp4"
    video.write_bytes(b"fake")

    with patch("video_tool.cli.video_commands.VideoProcessor") as mock_processor:
        mock_processor.return_value.cut_video.side_effect = RuntimeError("ffmpeg boom")
        result = runner.invoke(app, ["video", "cut", "-i", str(video), "-f", "10", "-t", "20"])

    assert result.exit_code == 1


@pytest.mark.unit
def test_cut_unsupported_format_exits_1(tmp_path: Path) -> None:
    weird = tmp_path / "notes.txt"
    weird.write_text("not a video")
    result = runner.invoke(app, ["video", "cut", "-i", str(weird), "-f", "10", "-t", "20"])
    assert result.exit_code == 1
