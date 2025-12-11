#!/usr/bin/env python3
"""Re-encode a source video to match a reference video's format for fast concat.

This script probes a reference video (video B) to capture container, video, and
audio characteristics, then reprocesses a source video (video A) so that
`ffmpeg -f concat -c copy` (the repo's `--fast-concat` flag) can be used
without re-encoding later.
"""

from __future__ import annotations

import argparse
import json
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

from loguru import logger


@dataclass
class VideoProfile:
    codec: str
    width: int
    height: int
    fps: float
    pix_fmt: Optional[str] = None
    profile: Optional[str] = None
    level: Optional[int] = None


@dataclass
class AudioProfile:
    codec: str
    sample_rate: int
    channels: int
    channel_layout: Optional[str] = None


FFMPEG_VIDEO_ENCODERS = {
    "h264": "libx264",
    "hevc": "libx265",
    "vp9": "libvpx-vp9",
    "av1": "libsvtav1",
}

FFMPEG_AUDIO_ENCODERS = {
    "aac": "aac",
    "mp3": "libmp3lame",
    "opus": "libopus",
    "vorbis": "libvorbis",
}


def _run_ffprobe(file_path: Path, selector: str, fields: str) -> Optional[dict]:
    """Run ffprobe for a single stream selector and return the first stream dict."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        selector,
        "-show_entries",
        f"stream={fields}",
        "-of",
        "json",
        str(file_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    payload = json.loads(result.stdout or "{}")
    streams = payload.get("streams") or []
    return streams[0] if streams else None


def _parse_fraction(value: Optional[str]) -> Optional[float]:
    """Convert ffprobe's fractional values (e.g., '30000/1001') into floats."""
    if not value:
        return None
    if "/" in value:
        numerator, denominator = value.split("/", maxsplit=1)
        try:
            return float(int(numerator) / int(denominator))
        except (ValueError, ZeroDivisionError):
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _format_level(raw_level: Optional[int | float | str]) -> Optional[str]:
    """FFmpeg expects levels like '4.1'; ffprobe often returns 41."""
    if raw_level is None:
        return None
    if isinstance(raw_level, (int, float)):
        if raw_level >= 10:
            return f"{raw_level / 10:.1f}".rstrip("0").rstrip(".")
        return str(raw_level)
    return str(raw_level)


def _extract_profiles(reference: Path) -> Tuple[VideoProfile, Optional[AudioProfile]]:
    """Probe the reference video to capture video and audio parameters."""
    video_data = _run_ffprobe(
        reference, "v:0", "codec_name,width,height,r_frame_rate,pix_fmt,profile,level"
    )
    if not video_data:
        raise RuntimeError(f"No video stream found in {reference}")

    fps = _parse_fraction(video_data.get("r_frame_rate")) or 30.0
    video_profile = VideoProfile(
        codec=video_data["codec_name"],
        width=int(video_data["width"]),
        height=int(video_data["height"]),
        fps=fps,
        pix_fmt=video_data.get("pix_fmt"),
        profile=video_data.get("profile"),
        level=video_data.get("level"),
    )

    audio_data = _run_ffprobe(
        reference, "a:0", "codec_name,sample_rate,channels,channel_layout"
    )
    audio_profile = None
    if audio_data:
        audio_profile = AudioProfile(
            codec=audio_data["codec_name"],
            sample_rate=int(audio_data["sample_rate"]),
            channels=int(audio_data["channels"]),
            channel_layout=audio_data.get("channel_layout"),
        )

    return video_profile, audio_profile


def _choose_video_encoder(codec: str) -> str:
    """Map codec names to sensible encoders."""
    return FFMPEG_VIDEO_ENCODERS.get(codec.lower(), codec)


def _choose_audio_encoder(codec: str) -> str:
    """Map codec names to sensible encoders."""
    return FFMPEG_AUDIO_ENCODERS.get(codec.lower(), codec)


def build_ffmpeg_command(
    source: Path, output: Path, video: VideoProfile, audio: Optional[AudioProfile]
) -> List[str]:
    """Create an ffmpeg command that aligns the source to the reference profile."""
    vf_parts = [f"scale={video.width}:{video.height}:flags=lanczos"]
    if video.fps:
        vf_parts.append(f"fps={video.fps:g}")
    vf_filter = ",".join(vf_parts)

    cmd: List[str] = [
        "ffmpeg",
        "-y",
        "-i",
        str(source),
        "-map",
        "0:v:0",
        "-vf",
        vf_filter,
        "-c:v",
        _choose_video_encoder(video.codec),
        "-pix_fmt",
        video.pix_fmt or "yuv420p",
        "-movflags",
        "+faststart",
    ]

    # Preserve profile/level when meaningful (helps stream-copy compatibility).
    if video.profile and video.codec.lower() in {"h264", "hevc"}:
        cmd.extend(["-profile:v", video.profile.lower()])
    formatted_level = _format_level(video.level)
    if formatted_level and video.codec.lower() in {"h264", "hevc"}:
        cmd.extend(["-level:v", formatted_level])

    if audio is None:
        cmd.append("-an")
    else:
        cmd.extend(
            [
                "-map",
                "0:a:0",
                "-c:a",
                _choose_audio_encoder(audio.codec),
                "-ar",
                str(audio.sample_rate),
                "-ac",
                str(audio.channels),
            ]
        )
        if audio.channel_layout:
            cmd.extend(["-channel_layout", audio.channel_layout])

    cmd.append(str(output))
    return cmd


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Re-encode video A to match video B so --fast-concat can stream copy."
    )
    parser.add_argument("source", help="Path to the video that needs reprocessing (video A).")
    parser.add_argument("reference", help="Path to the reference video to match (video B).")
    parser.add_argument(
        "-o",
        "--output",
        help="Optional output file path. Defaults to <source>_aligned<reference extension> in the source directory.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the ffmpeg command without executing it.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    source = Path(args.source).expanduser().resolve()
    reference = Path(args.reference).expanduser().resolve()

    if not source.exists():
        logger.error(f"Source video not found: {source}")
        sys.exit(1)
    if not reference.exists():
        logger.error(f"Reference video not found: {reference}")
        sys.exit(1)

    target_suffix = reference.suffix or ".mp4"
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
    else:
        output_path = source.with_name(f"{source.stem}_aligned{target_suffix}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(f"Probing reference video for profile: {reference}")
    video_profile, audio_profile = _extract_profiles(reference)

    ffmpeg_cmd = build_ffmpeg_command(source, output_path, video_profile, audio_profile)
    logger.info("FFmpeg command:")
    logger.info(shlex.join(ffmpeg_cmd))

    if args.dry_run:
        logger.info("Dry run: command not executed.")
        return

    logger.info(f"Re-encoding {source.name} to match {reference.name}")
    subprocess.run(ffmpeg_cmd, check=True)
    logger.success(f"Aligned video written to: {output_path}")
    logger.success(
        "You can now use `--fast-concat` with the reference video and the aligned output."
    )


if __name__ == "__main__":
    main()
