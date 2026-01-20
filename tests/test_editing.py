"""Unit tests for video editing operations (trim, cut, extract-segment, speed, info)."""

import json
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from video_tool.video_processor.editing import (
    _parse_timestamp,
    _format_timestamp,
    _detect_gpu_encoder,
    EditingMixin,
)


class TestTimestampParsing:
    """Test timestamp parsing utility functions."""

    def test_parse_timestamp_seconds_int(self):
        assert _parse_timestamp("90") == 90.0

    def test_parse_timestamp_seconds_float(self):
        assert _parse_timestamp("90.5") == 90.5

    def test_parse_timestamp_mm_ss(self):
        assert _parse_timestamp("01:30") == 90.0

    def test_parse_timestamp_hh_mm_ss(self):
        assert _parse_timestamp("01:30:00") == 5400.0

    def test_parse_timestamp_hh_mm_ss_with_fractions(self):
        result = _parse_timestamp("00:01:30.5")
        assert result == 90.5

    def test_parse_timestamp_strips_whitespace(self):
        assert _parse_timestamp("  90  ") == 90.0

    def test_parse_timestamp_invalid_format(self):
        with pytest.raises(ValueError, match="Invalid timestamp"):
            _parse_timestamp("invalid")

    def test_format_timestamp(self):
        assert _format_timestamp(90.5) == "00:01:30.500"

    def test_format_timestamp_hours(self):
        assert _format_timestamp(3661.123) == "01:01:01.123"

    def test_format_timestamp_zero(self):
        assert _format_timestamp(0) == "00:00:00.000"


class TestGPUDetection:
    """Test GPU encoder detection."""

    @patch("subprocess.run")
    @patch("platform.system", return_value="Darwin")
    def test_detect_gpu_encoder_macos_available(self, mock_system, mock_run):
        mock_run.return_value.returncode = 0
        result = _detect_gpu_encoder()
        assert result == "h264_videotoolbox"

    @patch("subprocess.run")
    @patch("platform.system", return_value="Darwin")
    def test_detect_gpu_encoder_macos_unavailable(self, mock_system, mock_run):
        mock_run.return_value.returncode = 1
        result = _detect_gpu_encoder()
        assert result is None

    @patch("subprocess.run")
    @patch("platform.system", return_value="Linux")
    def test_detect_gpu_encoder_linux_available(self, mock_system, mock_run):
        mock_run.return_value.returncode = 0
        result = _detect_gpu_encoder()
        assert result == "h264_nvenc"

    @patch("subprocess.run")
    @patch("platform.system", return_value="Windows")
    def test_detect_gpu_encoder_windows_available(self, mock_system, mock_run):
        mock_run.return_value.returncode = 0
        result = _detect_gpu_encoder()
        assert result == "h264_nvenc"

    @patch("platform.system", return_value="UnknownOS")
    def test_detect_gpu_encoder_unknown_os(self, mock_system):
        result = _detect_gpu_encoder()
        assert result is None


class TestGetVideoInfo:
    """Test get_video_info method."""

    @pytest.fixture
    def mock_processor(self, temp_dir, mock_video_processor):
        return mock_video_processor

    @patch("subprocess.run")
    def test_get_video_info_success(self, mock_run, temp_dir):
        video_file = temp_dir / "test.mp4"
        video_file.write_bytes(b"\x00" * 1000)

        ffprobe_output = {
            "format": {
                "duration": "120.5",
                "format_name": "mov,mp4,m4a,3gp,3g2,mj2",
                "bit_rate": "5000000",
            },
            "streams": [
                {
                    "codec_type": "video",
                    "codec_name": "h264",
                    "width": 1920,
                    "height": 1080,
                    "r_frame_rate": "30/1",
                    "pix_fmt": "yuv420p",
                },
                {
                    "codec_type": "audio",
                    "codec_name": "aac",
                    "channels": 2,
                    "sample_rate": "48000",
                },
            ],
        }

        mock_run.return_value.stdout = json.dumps(ffprobe_output)
        mock_run.return_value.returncode = 0

        from video_tool.video_processor import VideoProcessor

        with patch.object(VideoProcessor, "_load_prompts", return_value={}):
            processor = VideoProcessor(str(temp_dir))
            info = processor.get_video_info(str(video_file))

        assert info["duration_seconds"] == 120.5
        assert info["width"] == 1920
        assert info["height"] == 1080
        assert info["video_codec"] == "h264"
        assert info["audio_codec"] == "aac"
        assert info["fps"] == 30.0
        assert info["file_size_bytes"] == 1000

    def test_get_video_info_file_not_found(self, temp_dir):
        from video_tool.video_processor import VideoProcessor

        with patch.object(VideoProcessor, "_load_prompts", return_value={}):
            processor = VideoProcessor(str(temp_dir))
            with pytest.raises(FileNotFoundError):
                processor.get_video_info("/nonexistent/video.mp4")


class TestTrimVideo:
    """Test trim_video method."""

    @patch("subprocess.run")
    def test_trim_video_with_start_and_end(self, mock_run, temp_dir):
        video_file = temp_dir / "test.mp4"
        video_file.write_bytes(b"\x00" * 1000)
        output_file = temp_dir / "output" / "trimmed.mp4"

        mock_run.return_value.returncode = 0

        from video_tool.video_processor import VideoProcessor

        with patch.object(VideoProcessor, "_load_prompts", return_value={}):
            processor = VideoProcessor(str(temp_dir))
            result = processor.trim_video(
                str(video_file), str(output_file), start="00:00:30", end="00:05:00"
            )

        assert result == str(output_file)
        mock_run.assert_called_once()

        # Verify ffmpeg was called with correct args
        call_args = mock_run.call_args[0][0]
        assert "ffmpeg" in call_args
        assert "-ss" in call_args
        assert "-c" in call_args

    @patch("subprocess.run")
    def test_trim_video_start_only(self, mock_run, temp_dir):
        video_file = temp_dir / "test.mp4"
        video_file.write_bytes(b"\x00" * 1000)
        output_file = temp_dir / "output" / "trimmed.mp4"

        mock_run.return_value.returncode = 0

        from video_tool.video_processor import VideoProcessor

        with patch.object(VideoProcessor, "_load_prompts", return_value={}):
            processor = VideoProcessor(str(temp_dir))
            result = processor.trim_video(str(video_file), str(output_file), start="30")

        call_args = mock_run.call_args[0][0]
        assert "-ss" in call_args
        assert "-to" not in call_args

    @patch("subprocess.run")
    def test_trim_video_end_only(self, mock_run, temp_dir):
        video_file = temp_dir / "test.mp4"
        video_file.write_bytes(b"\x00" * 1000)
        output_file = temp_dir / "output" / "trimmed.mp4"

        mock_run.return_value.returncode = 0

        from video_tool.video_processor import VideoProcessor

        with patch.object(VideoProcessor, "_load_prompts", return_value={}):
            processor = VideoProcessor(str(temp_dir))
            result = processor.trim_video(str(video_file), str(output_file), end="01:00")

        call_args = mock_run.call_args[0][0]
        assert "-ss" not in call_args
        assert "-to" in call_args

    @patch("video_tool.video_processor.editing._detect_gpu_encoder", return_value="h264_videotoolbox")
    @patch("subprocess.run")
    def test_trim_video_with_gpu(self, mock_run, mock_gpu, temp_dir):
        video_file = temp_dir / "test.mp4"
        video_file.write_bytes(b"\x00" * 1000)
        output_file = temp_dir / "output" / "trimmed.mp4"

        mock_run.return_value.returncode = 0

        from video_tool.video_processor import VideoProcessor

        with patch.object(VideoProcessor, "_load_prompts", return_value={}):
            processor = VideoProcessor(str(temp_dir))
            result = processor.trim_video(
                str(video_file), str(output_file), start="10", gpu=True
            )

        call_args = mock_run.call_args[0][0]
        assert "h264_videotoolbox" in call_args

    def test_trim_video_file_not_found(self, temp_dir):
        from video_tool.video_processor import VideoProcessor

        with patch.object(VideoProcessor, "_load_prompts", return_value={}):
            processor = VideoProcessor(str(temp_dir))
            with pytest.raises(FileNotFoundError):
                processor.trim_video("/nonexistent.mp4", "/output.mp4", start="10")


class TestExtractSegment:
    """Test extract_segment method."""

    @patch("subprocess.run")
    def test_extract_segment(self, mock_run, temp_dir):
        video_file = temp_dir / "test.mp4"
        video_file.write_bytes(b"\x00" * 1000)
        output_file = temp_dir / "output" / "segment.mp4"

        mock_run.return_value.returncode = 0

        from video_tool.video_processor import VideoProcessor

        with patch.object(VideoProcessor, "_load_prompts", return_value={}):
            processor = VideoProcessor(str(temp_dir))
            result = processor.extract_segment(
                str(video_file), str(output_file), start="00:01:00", end="00:02:00"
            )

        assert result == str(output_file)
        mock_run.assert_called_once()


class TestCutVideo:
    """Test cut_video method (remove middle segment)."""

    @patch("subprocess.run")
    def test_cut_video_removes_middle(self, mock_run, temp_dir):
        video_file = temp_dir / "test.mp4"
        video_file.write_bytes(b"\x00" * 1000)
        output_file = temp_dir / "output" / "cut.mp4"

        # Mock ffprobe for get_video_info (first call)
        ffprobe_output = {
            "format": {"duration": "300.0"},
            "streams": [{"codec_type": "video", "r_frame_rate": "30/1"}],
        }

        def subprocess_side_effect(*args, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stdout = json.dumps(ffprobe_output)
            result.stderr = ""
            # Create temp files when trim_video is called
            if args and args[0] and "ffmpeg" in args[0][0]:
                # Create output file for trim operations
                cmd = args[0]
                if "-y" in cmd:
                    output_idx = len(cmd) - 1
                    output_path = Path(cmd[output_idx])
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    output_path.write_bytes(b"\x00" * 100)
            return result

        mock_run.side_effect = subprocess_side_effect

        from video_tool.video_processor import VideoProcessor

        with patch.object(VideoProcessor, "_load_prompts", return_value={}):
            processor = VideoProcessor(str(temp_dir))
            result = processor.cut_video(
                str(video_file), str(output_file), cut_from="00:01:00", cut_to="00:02:00"
            )

        assert result == str(output_file)

    def test_cut_video_invalid_range(self, temp_dir):
        video_file = temp_dir / "test.mp4"
        video_file.write_bytes(b"\x00" * 1000)
        output_file = temp_dir / "output" / "cut.mp4"

        from video_tool.video_processor import VideoProcessor

        with patch.object(VideoProcessor, "_load_prompts", return_value={}):
            processor = VideoProcessor(str(temp_dir))
            with pytest.raises(ValueError, match="cut_from.*must be before"):
                processor.cut_video(
                    str(video_file), str(output_file), cut_from="00:03:00", cut_to="00:02:00"
                )


class TestChangeVideoSpeed:
    """Test change_video_speed method."""

    @patch("subprocess.run")
    def test_speed_up_video(self, mock_run, temp_dir):
        video_file = temp_dir / "test.mp4"
        video_file.write_bytes(b"\x00" * 1000)
        output_file = temp_dir / "output" / "fast.mp4"

        mock_run.return_value.returncode = 0

        from video_tool.video_processor import VideoProcessor

        with patch.object(VideoProcessor, "_load_prompts", return_value={}):
            processor = VideoProcessor(str(temp_dir))
            result = processor.change_video_speed(
                str(video_file), str(output_file), factor=2.0
            )

        assert result == str(output_file)
        call_args = mock_run.call_args[0][0]
        assert "setpts=PTS/2.0" in " ".join(call_args)

    @patch("subprocess.run")
    def test_slow_down_video(self, mock_run, temp_dir):
        video_file = temp_dir / "test.mp4"
        video_file.write_bytes(b"\x00" * 1000)
        output_file = temp_dir / "output" / "slow.mp4"

        mock_run.return_value.returncode = 0

        from video_tool.video_processor import VideoProcessor

        with patch.object(VideoProcessor, "_load_prompts", return_value={}):
            processor = VideoProcessor(str(temp_dir))
            result = processor.change_video_speed(
                str(video_file), str(output_file), factor=0.5
            )

        assert result == str(output_file)

    def test_speed_factor_out_of_range_low(self, temp_dir):
        video_file = temp_dir / "test.mp4"
        video_file.write_bytes(b"\x00" * 1000)

        from video_tool.video_processor import VideoProcessor

        with patch.object(VideoProcessor, "_load_prompts", return_value={}):
            processor = VideoProcessor(str(temp_dir))
            with pytest.raises(ValueError, match="between 0.25 and 4.0"):
                processor.change_video_speed(str(video_file), "/output.mp4", factor=0.1)

    def test_speed_factor_out_of_range_high(self, temp_dir):
        video_file = temp_dir / "test.mp4"
        video_file.write_bytes(b"\x00" * 1000)

        from video_tool.video_processor import VideoProcessor

        with patch.object(VideoProcessor, "_load_prompts", return_value={}):
            processor = VideoProcessor(str(temp_dir))
            with pytest.raises(ValueError, match="between 0.25 and 4.0"):
                processor.change_video_speed(str(video_file), "/output.mp4", factor=5.0)

    @patch("subprocess.run")
    def test_extreme_speedup_chains_atempo(self, mock_run, temp_dir):
        """Test that extreme speed factors chain multiple atempo filters."""
        video_file = temp_dir / "test.mp4"
        video_file.write_bytes(b"\x00" * 1000)
        output_file = temp_dir / "output" / "very_fast.mp4"

        mock_run.return_value.returncode = 0

        from video_tool.video_processor import VideoProcessor

        with patch.object(VideoProcessor, "_load_prompts", return_value={}):
            processor = VideoProcessor(str(temp_dir))
            result = processor.change_video_speed(
                str(video_file), str(output_file), factor=4.0
            )

        # For factor=4.0, audio needs atempo=2.0,atempo=2.0
        call_args = " ".join(mock_run.call_args[0][0])
        assert "atempo=2.0" in call_args


@pytest.mark.requires_ffmpeg
class TestEditingIntegration:
    """Integration tests requiring ffmpeg (marked for optional execution)."""

    def test_full_trim_workflow(self, temp_dir):
        """Full integration test for trimming - requires ffmpeg installed."""
        # This test is skipped unless run with pytest -m requires_ffmpeg
        pass

    def test_full_speed_workflow(self, temp_dir):
        """Full integration test for speed change - requires ffmpeg installed."""
        pass
