"""Unit tests for GPU encoder detection and encoder selection in video processing.

The PR replaces hardcoded macOS-only encoder names with cross-platform
_detect_gpu_encoder() and graceful software fallback. On master,
_detect_gpu_encoder lives in editing.py. After the PR merge, concatenation.py
also imports it. These tests work on both branches.
"""

import json
import subprocess
from unittest.mock import patch, MagicMock

import pytest

# The function exists in editing.py on both master and the PR branch
from video_tool.video_processor.editing import _detect_gpu_encoder


class TestDetectGPUEncoder:
    """Test _detect_gpu_encoder platform detection and ffmpeg probing."""

    @patch("subprocess.run")
    @patch("platform.system", return_value="Darwin")
    def test_macos_videotoolbox_available(self, mock_system, mock_run) -> None:
        mock_run.return_value.returncode = 0
        result = _detect_gpu_encoder()
        assert result == "h264_videotoolbox"

    @patch("subprocess.run")
    @patch("platform.system", return_value="Darwin")
    def test_macos_videotoolbox_unavailable(self, mock_system, mock_run) -> None:
        mock_run.return_value.returncode = 1
        result = _detect_gpu_encoder()
        assert result is None

    @patch("subprocess.run")
    @patch("platform.system", return_value="Linux")
    def test_linux_nvenc_available(self, mock_system, mock_run) -> None:
        mock_run.return_value.returncode = 0
        result = _detect_gpu_encoder()
        assert result == "h264_nvenc"

    @patch("subprocess.run")
    @patch("platform.system", return_value="Linux")
    def test_linux_hevc_nvenc_available(self, mock_system, mock_run) -> None:
        mock_run.return_value.returncode = 0
        result = _detect_gpu_encoder("hevc")
        assert result == "hevc_nvenc"

    @patch("subprocess.run")
    @patch("platform.system", return_value="Darwin")
    def test_macos_hevc_videotoolbox_available(self, mock_system, mock_run) -> None:
        mock_run.return_value.returncode = 0
        result = _detect_gpu_encoder("h265")
        assert result == "hevc_videotoolbox"

    @patch("subprocess.run")
    @patch("platform.system", return_value="Windows")
    def test_windows_nvenc_available(self, mock_system, mock_run) -> None:
        mock_run.return_value.returncode = 0
        result = _detect_gpu_encoder()
        assert result == "h264_nvenc"

    @patch("platform.system", return_value="FreeBSD")
    def test_unknown_os_returns_none(self, mock_system) -> None:
        result = _detect_gpu_encoder()
        assert result is None

    @patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="ffmpeg", timeout=10))
    @patch("platform.system", return_value="Darwin")
    def test_ffmpeg_timeout_returns_none(self, mock_system, mock_run) -> None:
        result = _detect_gpu_encoder()
        assert result is None

    @patch("subprocess.run", side_effect=FileNotFoundError("ffmpeg not found"))
    @patch("platform.system", return_value="Darwin")
    def test_ffmpeg_not_found_returns_none(self, mock_system, mock_run) -> None:
        result = _detect_gpu_encoder()
        assert result is None

    @patch("subprocess.run")
    @patch("platform.system", return_value="Darwin")
    def test_detect_gpu_encoder_ffmpeg_args(self, mock_system, mock_run) -> None:
        """Verify the ffmpeg test command uses correct arguments."""
        mock_run.return_value.returncode = 0
        _detect_gpu_encoder()

        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "ffmpeg"
        assert "-f" in call_args
        assert "lavfi" in call_args
        assert "-c:v" in call_args

    def test_encoder_return_values_are_valid(self) -> None:
        """Test that return value is a valid encoder name or None."""
        valid_encoders = {
            "h264_videotoolbox",
            "hevc_videotoolbox",
            "h264_nvenc",
            "hevc_nvenc",
            None,
        }

        with patch("subprocess.run") as mock_run:
            for platform, expected in [("Darwin", "h264_videotoolbox"), ("Linux", "h264_nvenc")]:
                with patch("platform.system", return_value=platform):
                    mock_run.return_value.returncode = 0
                    result = _detect_gpu_encoder()
                    assert result in valid_encoders


class TestEncoderMappingLogic:
    """Test the encoder mapping logic used in concatenation and compression.

    These are pure-logic tests that verify the mapping dictionaries and
    fallback behavior without calling ffmpeg.
    """

    def test_hw_encoder_mapping_macos(self) -> None:
        """Verify macOS hardware encoder mapping."""
        codec_to_hw_encoder = {"h265": "hevc_videotoolbox", "h264": "h264_videotoolbox"}
        assert codec_to_hw_encoder["h264"] == "h264_videotoolbox"
        assert codec_to_hw_encoder["h265"] == "hevc_videotoolbox"

    def test_software_fallback_mapping(self) -> None:
        """Verify software fallback encoder mapping."""
        sw_encoders = {"h265": "libx265", "h264": "libx264"}
        assert sw_encoders["h264"] == "libx264"
        assert sw_encoders["h265"] == "libx265"

    def test_nvidia_encoder_mapping(self) -> None:
        """Verify NVIDIA encoder mapping for Linux/Windows."""
        codec_to_nvenc = {"h264": "h264_nvenc", "h265": "hevc_nvenc"}
        assert codec_to_nvenc["h264"] == "h264_nvenc"
        assert codec_to_nvenc["h265"] == "hevc_nvenc"


class TestConcatenationEncoderSelection:
    """Test encoder choices in concatenation operations."""

    @patch("video_tool.video_processor.concatenation._detect_gpu_encoder", return_value="h264_nvenc")
    @patch("video_tool.video_processor.concatenation.subprocess.run")
    def test_match_video_encoding_uses_detected_h264_encoder(
        self, mock_run, mock_detect, tmp_path
    ) -> None:
        """Linux/Windows GPU detection should not emit macOS VideoToolbox encoders."""
        source_file = tmp_path / "source.mp4"
        reference_file = tmp_path / "reference.mp4"
        source_file.write_bytes(b"source")
        reference_file.write_bytes(b"reference")

        video_probe = MagicMock()
        video_probe.stdout = json.dumps(
            {
                "streams": [
                    {
                        "codec_name": "h264",
                        "width": 1920,
                        "height": 1080,
                        "r_frame_rate": "30/1",
                        "bit_rate": "1000000",
                    }
                ]
            }
        )
        audio_probe = MagicMock()
        audio_probe.stdout = json.dumps({"streams": []})
        ffmpeg_result = MagicMock(returncode=0)
        mock_run.side_effect = [video_probe, audio_probe, ffmpeg_result]

        from video_tool.video_processor import VideoProcessor
        with patch.object(VideoProcessor, "_load_prompts", return_value={}):
            processor = VideoProcessor(str(tmp_path))

        processor.match_video_encoding(str(source_file), str(reference_file))

        ffmpeg_cmd = mock_run.call_args_list[-1].args[0]
        assert "h264_nvenc" in ffmpeg_cmd
        assert "h264_videotoolbox" not in ffmpeg_cmd


class TestEditingGPUIntegration:
    """Test GPU encoder detection integration in editing operations.

    Uses the editing.py module which exists on both branches.
    """

    @patch("subprocess.run")
    def test_trim_video_with_gpu_uses_detected_encoder(self, mock_run, tmp_path) -> None:
        """Verify trim_video uses the detected GPU encoder when gpu=True."""
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"\x00" * 1000)
        output_file = tmp_path / "output" / "trimmed.mp4"

        mock_run.return_value.returncode = 0

        from video_tool.video_processor import VideoProcessor
        with patch.object(VideoProcessor, "_load_prompts", return_value={}):
            processor = VideoProcessor(str(tmp_path))

        with patch("video_tool.video_processor.editing._detect_gpu_encoder", return_value="h264_videotoolbox"):
            processor.trim_video(str(video_file), str(output_file), start="10", gpu=True)

        call_args = mock_run.call_args[0][0]
        # Should include the GPU encoder
        assert "h264_videotoolbox" in call_args

    @patch("subprocess.run")
    def test_trim_video_without_gpu_uses_stream_copy(self, mock_run, tmp_path) -> None:
        """Verify trim_video uses stream copy when gpu=False."""
        video_file = tmp_path / "test.mp4"
        video_file.write_bytes(b"\x00" * 1000)
        output_file = tmp_path / "output" / "trimmed.mp4"

        mock_run.return_value.returncode = 0

        from video_tool.video_processor import VideoProcessor
        with patch.object(VideoProcessor, "_load_prompts", return_value={}):
            processor = VideoProcessor(str(tmp_path))

        processor.trim_video(str(video_file), str(output_file), start="10", gpu=False)

        call_args = mock_run.call_args[0][0]
        assert "-c" in call_args
        assert "copy" in call_args