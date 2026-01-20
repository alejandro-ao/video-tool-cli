"""Video editing operations: info, trim, cut, extract-segment, speed."""

from __future__ import annotations

import json
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from .shared import logger


def _detect_gpu_encoder() -> Optional[str]:
    """Detect available hardware video encoder.

    Returns encoder name (h264_videotoolbox, h264_nvenc) or None if unavailable.
    """
    system = platform.system()

    if system == "Darwin":
        encoder = "h264_videotoolbox"
    elif system in ("Linux", "Windows"):
        encoder = "h264_nvenc"
    else:
        return None

    # Test if encoder is available
    try:
        result = subprocess.run(
            [
                "ffmpeg", "-f", "lavfi", "-i", "testsrc=duration=0.1:size=64x64:rate=1",
                "-c:v", encoder, "-t", "0.1", "-f", "null", "-"
            ],
            capture_output=True,
            timeout=10,
        )
        if result.returncode == 0:
            return encoder
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return None


def _parse_timestamp(ts: str) -> float:
    """Parse timestamp string to seconds.

    Accepts: HH:MM:SS, MM:SS, or seconds (as string or float).
    """
    ts = ts.strip()

    # Try parsing as float (seconds)
    try:
        return float(ts)
    except ValueError:
        pass

    # Parse time format
    parts = ts.split(":")
    if len(parts) == 2:
        # MM:SS
        minutes, seconds = parts
        return int(minutes) * 60 + float(seconds)
    elif len(parts) == 3:
        # HH:MM:SS
        hours, minutes, seconds = parts
        return int(hours) * 3600 + int(minutes) * 60 + float(seconds)

    raise ValueError(f"Invalid timestamp format: {ts}")


def _format_timestamp(seconds: float) -> str:
    """Format seconds as HH:MM:SS.mmm for ffmpeg."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{secs:06.3f}"


class EditingMixin:
    """Video editing operations: trim, cut, extract-segment, speed, info."""

    def get_video_info(self, video_path: str) -> Dict[str, Any]:
        """Get detailed video metadata using ffprobe.

        Returns dict with: duration, resolution, fps, codec, bitrate, audio_channels, file_size
        """
        path = Path(video_path)
        if not path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        logger.info(f"Getting video info: {path.name}")

        # Get format and stream info
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", str(path)
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)

        # Extract format info
        fmt = data.get("format", {})
        streams = data.get("streams", [])

        # Find video and audio streams
        video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
        audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

        info: Dict[str, Any] = {
            "file_path": str(path.absolute()),
            "file_name": path.name,
            "file_size_bytes": path.stat().st_size,
            "file_size_mb": round(path.stat().st_size / (1024 * 1024), 2),
            "duration_seconds": float(fmt.get("duration", 0)),
            "format_name": fmt.get("format_name"),
            "bit_rate": int(fmt.get("bit_rate", 0)) if fmt.get("bit_rate") else None,
        }

        if video_stream:
            # Parse frame rate
            fps_str = video_stream.get("r_frame_rate", "0/1")
            try:
                num, den = fps_str.split("/")
                fps = float(num) / float(den) if float(den) != 0 else 0
            except (ValueError, ZeroDivisionError):
                fps = 0

            info.update({
                "width": video_stream.get("width"),
                "height": video_stream.get("height"),
                "resolution": f"{video_stream.get('width')}x{video_stream.get('height')}",
                "video_codec": video_stream.get("codec_name"),
                "fps": round(fps, 2),
                "pixel_format": video_stream.get("pix_fmt"),
            })

        if audio_stream:
            info.update({
                "audio_codec": audio_stream.get("codec_name"),
                "audio_channels": audio_stream.get("channels"),
                "audio_sample_rate": int(audio_stream.get("sample_rate", 0)) if audio_stream.get("sample_rate") else None,
            })

        # Format duration as HH:MM:SS
        duration = info["duration_seconds"]
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        secs = duration % 60
        info["duration_formatted"] = f"{hours:02d}:{minutes:02d}:{secs:05.2f}"

        return info

    def trim_video(
        self,
        video_path: str,
        output_path: str,
        start: Optional[str] = None,
        end: Optional[str] = None,
        gpu: bool = False,
    ) -> str:
        """Trim video by cutting start and/or end.

        Args:
            video_path: Input video file path
            output_path: Output video file path
            start: Start timestamp (default: beginning)
            end: End timestamp (default: end of video)
            gpu: Use GPU acceleration if available

        Returns:
            Path to output file
        """
        input_path = Path(video_path)
        out_path = Path(output_path)

        if not input_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        out_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Trimming video: {input_path.name}")

        cmd = ["ffmpeg", "-y"]

        # Add start position (before -i for fast seeking)
        if start:
            start_seconds = _parse_timestamp(start)
            cmd.extend(["-ss", _format_timestamp(start_seconds)])

        cmd.extend(["-i", str(input_path)])

        # Add end position
        if end:
            end_seconds = _parse_timestamp(end)
            if start:
                # Duration from start
                duration = end_seconds - _parse_timestamp(start)
                cmd.extend(["-t", str(duration)])
            else:
                cmd.extend(["-to", _format_timestamp(end_seconds)])

        # Encoding options
        if gpu:
            encoder = _detect_gpu_encoder()
            if encoder:
                logger.info(f"Using GPU encoder: {encoder}")
                cmd.extend(["-c:v", encoder, "-c:a", "aac"])
            else:
                logger.warning("GPU encoder not available, using stream copy")
                cmd.extend(["-c", "copy"])
        else:
            # Use stream copy for speed (no re-encoding)
            cmd.extend(["-c", "copy"])

        cmd.extend(["-avoid_negative_ts", "make_zero", str(out_path)])

        logger.debug(f"FFmpeg command: {' '.join(cmd)}")

        try:
            subprocess.run(cmd, check=True, **self._quiet_subprocess_kwargs())
            logger.info(f"Trimmed video saved to: {out_path}")
            return str(out_path)
        except subprocess.CalledProcessError as exc:
            logger.error(f"Failed to trim video: {exc}")
            if hasattr(exc, 'stderr') and exc.stderr:
                logger.error(f"FFmpeg stderr: {exc.stderr}")
            raise

    def extract_segment(
        self,
        video_path: str,
        output_path: str,
        start: str,
        end: str,
        gpu: bool = False,
    ) -> str:
        """Extract a segment from video (keep only specified range).

        Args:
            video_path: Input video file path
            output_path: Output video file path
            start: Start timestamp
            end: End timestamp
            gpu: Use GPU acceleration if available

        Returns:
            Path to output file
        """
        # extract_segment is functionally same as trim with both start and end
        return self.trim_video(video_path, output_path, start=start, end=end, gpu=gpu)

    def cut_video(
        self,
        video_path: str,
        output_path: str,
        cut_from: str,
        cut_to: str,
        gpu: bool = False,
    ) -> str:
        """Remove a segment from video (keep before and after, remove middle).

        Args:
            video_path: Input video file path
            output_path: Output video file path
            cut_from: Start of segment to remove
            cut_to: End of segment to remove
            gpu: Use GPU acceleration if available

        Returns:
            Path to output file
        """
        input_path = Path(video_path)
        out_path = Path(output_path)

        if not input_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        out_path.parent.mkdir(parents=True, exist_ok=True)

        from_seconds = _parse_timestamp(cut_from)
        to_seconds = _parse_timestamp(cut_to)

        if from_seconds >= to_seconds:
            raise ValueError(f"cut_from ({cut_from}) must be before cut_to ({cut_to})")

        logger.info(f"Cutting segment {cut_from} to {cut_to} from: {input_path.name}")

        # Get video duration
        info = self.get_video_info(video_path)
        duration = info["duration_seconds"]

        # Create temp directory for intermediate files
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            segments: List[Path] = []

            # Extract part before cut (if cut doesn't start at beginning)
            if from_seconds > 0.1:
                before_path = temp_path / "before.mp4"
                self.trim_video(video_path, str(before_path), end=cut_from, gpu=gpu)
                if before_path.exists() and before_path.stat().st_size > 0:
                    segments.append(before_path)

            # Extract part after cut (if cut doesn't end at the end)
            if to_seconds < duration - 0.1:
                after_path = temp_path / "after.mp4"
                self.trim_video(video_path, str(after_path), start=cut_to, gpu=gpu)
                if after_path.exists() and after_path.stat().st_size > 0:
                    segments.append(after_path)

            if not segments:
                raise ValueError("Cut would remove entire video")

            if len(segments) == 1:
                # Only one segment, just copy it
                shutil.copy2(segments[0], out_path)
            else:
                # Concatenate segments
                concat_list = temp_path / "concat_list.txt"
                with open(concat_list, "w") as f:
                    for seg in segments:
                        f.write(f"file '{seg}'\n")

                cmd = [
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(concat_list), "-c", "copy", str(out_path)
                ]

                subprocess.run(cmd, check=True, **self._quiet_subprocess_kwargs())

        logger.info(f"Cut video saved to: {out_path}")
        return str(out_path)

    def change_video_speed(
        self,
        video_path: str,
        output_path: str,
        factor: float,
        preserve_pitch: bool = True,
        gpu: bool = False,
    ) -> str:
        """Change video playback speed.

        Args:
            video_path: Input video file path
            output_path: Output video file path
            factor: Speed multiplier (0.25-4.0). 2.0 = 2x speed, 0.5 = half speed
            preserve_pitch: Preserve audio pitch when changing speed (default True)
            gpu: Use GPU acceleration if available

        Returns:
            Path to output file
        """
        input_path = Path(video_path)
        out_path = Path(output_path)

        if not input_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        if factor < 0.25 or factor > 4.0:
            raise ValueError(f"Speed factor must be between 0.25 and 4.0, got {factor}")

        out_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Changing video speed to {factor}x: {input_path.name}")

        # Video filter: setpts adjusts presentation timestamps
        # For speedup (factor > 1): PTS / factor = faster
        # For slowdown (factor < 1): PTS / factor = slower
        video_filter = f"setpts=PTS/{factor}"

        # Audio filter: atempo
        # atempo only supports 0.5-2.0, chain multiple for extremes
        audio_filters = []
        remaining_factor = factor

        while remaining_factor > 2.0:
            audio_filters.append("atempo=2.0")
            remaining_factor /= 2.0
        while remaining_factor < 0.5:
            audio_filters.append("atempo=0.5")
            remaining_factor /= 0.5

        if remaining_factor != 1.0:
            audio_filters.append(f"atempo={remaining_factor}")

        # Build command
        cmd = ["ffmpeg", "-y", "-i", str(input_path)]

        # Add filters
        filter_complex = f"[0:v]{video_filter}[v]"
        if audio_filters:
            audio_chain = ",".join(audio_filters)
            filter_complex += f";[0:a]{audio_chain}[a]"
            cmd.extend(["-filter_complex", filter_complex, "-map", "[v]", "-map", "[a]"])
        else:
            cmd.extend(["-vf", video_filter, "-af", "aresample=async=1"])

        # Encoding
        if gpu:
            encoder = _detect_gpu_encoder()
            if encoder:
                logger.info(f"Using GPU encoder: {encoder}")
                cmd.extend(["-c:v", encoder])
            else:
                logger.warning("GPU encoder not available, using libx264")
                cmd.extend(["-c:v", "libx264", "-preset", "fast"])
        else:
            cmd.extend(["-c:v", "libx264", "-preset", "fast"])

        cmd.extend(["-c:a", "aac", str(out_path)])

        logger.debug(f"FFmpeg command: {' '.join(cmd)}")

        try:
            subprocess.run(cmd, check=True, **self._quiet_subprocess_kwargs())
            logger.info(f"Speed-adjusted video saved to: {out_path}")
            return str(out_path)
        except subprocess.CalledProcessError as exc:
            logger.error(f"Failed to change video speed: {exc}")
            if hasattr(exc, 'stderr') and exc.stderr:
                logger.error(f"FFmpeg stderr: {exc.stderr}")
            raise
