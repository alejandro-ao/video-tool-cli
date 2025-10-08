from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from .shared import VideoFileClip, logger


class ConcatenationMixin:
    """Video concatenation, timestamp generation, and encoding utilities."""

    def concatenate_videos(
        self,
        output_filename: Optional[str] = None,
        skip_reprocessing: bool = False,
    ) -> str:
        """Concatenate multiple MP4 videos in alphabetical order using ffmpeg."""
        processed_dir = self.input_dir / "processed"
        mp4_files: List[Path] = []

        if processed_dir.exists():
            try:
                mp4_files = self.get_mp4_files(str(processed_dir))
                logger.info(f"Using videos from processed directory: {processed_dir}")
            except ValueError:
                pass

        if not mp4_files:
            mp4_files = self.get_mp4_files()
            logger.info(f"Using videos from input directory: {self.input_dir}")

        if not mp4_files:
            logger.warning(
                f"No MP4 files found in either the processed directory ({processed_dir}) "
                f"or input directory ({self.input_dir})"
            )
            video_info = {
                "timestamps": [],
                "metadata": {
                    "creation_date": datetime.now().isoformat(),
                },
            }
            output_path = self.output_dir / "timestamps.json"
            with open(output_path, "w") as file:
                json.dump([video_info], file, indent=2)
            return video_info

        logger.info(f"Found {len(mp4_files)} MP4 files to concatenate")

        output_filename = self._determine_output_filename(output_filename)
        output_path = self._resolve_unique_output_path(output_filename)
        temp_dir = self.input_dir / "temp_processed"
        temp_dir.mkdir(exist_ok=True)

        try:
            if skip_reprocessing:
                logger.info("Fast concatenation mode: skipping video reprocessing")
                concat_list = temp_dir / "concat_list.txt"
                with open(concat_list, "w") as file:
                    for mp4_file in mp4_files:
                        file.write(f"file '{mp4_file.resolve()}'\n")

                logger.info("Concatenating videos without reprocessing")
                subprocess.run(
                    [
                        "ffmpeg",
                        "-f",
                        "concat",
                        "-safe",
                        "0",
                        "-i",
                        str(concat_list),
                        "-c",
                        "copy",
                        str(output_path),
                    ],
                    check=True,
                    **self._quiet_subprocess_kwargs(),
                )
            else:
                logger.info(
                    "Standard concatenation mode: reprocessing videos for compatibility"
                )

                probe_cmd = [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "v:0",
                    "-show_entries",
                    "stream=width,height,r_frame_rate,codec_name",
                    "-of",
                    "json",
                    str(mp4_files[0]),
                ]
                probe_result = subprocess.run(
                    probe_cmd, capture_output=True, text=True, check=True
                )
                video_info = json.loads(probe_result.stdout)
                stream_info = video_info["streams"][0]

                audio_probe_cmd = [
                    "ffprobe",
                    "-v",
                    "error",
                    "-select_streams",
                    "a:0",
                    "-show_entries",
                    "stream=codec_name,sample_rate,channels",
                    "-of",
                    "json",
                    str(mp4_files[0]),
                ]
                audio_result = subprocess.run(
                    audio_probe_cmd, capture_output=True, text=True, check=True
                )
                audio_info = json.loads(audio_result.stdout)
                audio_stream = audio_info["streams"][0] if audio_info["streams"] else None

                processed_files: List[Path] = []
                for mp4_file in mp4_files:
                    output_file = temp_dir / f"processed_{mp4_file.name}"
                    numerator, denominator = stream_info["r_frame_rate"].split("/")
                    fps = float(int(numerator) / int(denominator))

                    cmd = [
                        "ffmpeg",
                        "-hwaccel",
                        "auto",
                        "-i",
                        str(mp4_file),
                        "-c:v",
                        "h264_videotoolbox"
                        if stream_info["codec_name"] == "h264"
                        else stream_info["codec_name"],
                        "-s",
                        f"{stream_info['width']}x{stream_info['height']}",
                        "-r",
                        str(fps),
                        "-preset",
                        "fast",
                        "-profile:v",
                        "high",
                    ]

                    if audio_stream:
                        cmd.extend(
                            [
                                "-c:a",
                                audio_stream["codec_name"],
                                "-ar",
                                audio_stream["sample_rate"],
                                "-ac",
                                str(audio_stream["channels"]),
                            ]
                        )

                    cmd.extend(["-y", str(output_file)])
                    logger.info(
                        f"Standardizing video with hardware acceleration: {mp4_file.name}"
                    )
                    subprocess.run(
                        cmd,
                        check=True,
                        **self._quiet_subprocess_kwargs(),
                    )
                    processed_files.append(output_file)

                concat_list = temp_dir / "concat_list.txt"
                with open(concat_list, "w") as file:
                    for processed_file in processed_files:
                        file.write(f"file '{processed_file.name}'\n")

                logger.info("Concatenating standardized videos")
                subprocess.run(
                    [
                        "ffmpeg",
                        "-f",
                        "concat",
                        "-safe",
                        "0",
                        "-i",
                        str(concat_list),
                        "-c",
                        "copy",
                        str(output_path),
                    ],
                    check=True,
                    **self._quiet_subprocess_kwargs(),
                )

            self.last_output_path = output_path
            return str(output_path)
        except subprocess.CalledProcessError as exc:
            logger.error(f"Error during video processing: {exc}")
            if exc.stderr:
                logger.error(f"FFmpeg stderr: {exc.stderr}")
            raise
        finally:
            if temp_dir.exists():
                for temp_file in temp_dir.glob("*"):
                    temp_file.unlink()
                temp_dir.rmdir()

    def generate_timestamps(self) -> Dict:
        """Generate timestamp information for the video with chapters based on input videos."""
        processed_dir = self.input_dir / "processed"
        mp4_files: List[Path] = []

        if processed_dir.exists():
            try:
                mp4_files = self.get_mp4_files(str(processed_dir))
                logger.info(
                    f"Generating timestamps from processed directory: {processed_dir}"
                )
            except ValueError:
                pass

        if not mp4_files:
            mp4_files = self.get_mp4_files()
            if callable(getattr(logger, "__call__", None)):
                logger("Generating timestamps from input directory")
            logger.info(f"Generating timestamps from input directory: {self.input_dir}")

        if not mp4_files:
            logger.warning(
                f"No MP4 files found in either the processed directory ({processed_dir}) "
                f"or input directory ({self.input_dir})"
            )
            video_info = {
                "timestamps": [],
                "metadata": {
                    "creation_date": datetime.now().isoformat(),
                },
            }
            output_path = self.output_dir / "timestamps.json"
            with open(output_path, "w") as file:
                json.dump([video_info], file, indent=2)
            return video_info

        timestamps = []
        current_time = 0

        for mp4_file in mp4_files:
            duration = None
            try:
                meta = self._get_video_metadata(str(mp4_file))
                if isinstance(meta, dict):
                    duration = int(meta.get("duration", 0)) if meta.get("duration") else None
                elif isinstance(meta, tuple) and len(meta) == 3 and meta[2] is not None:
                    duration = int(meta[2] * 60)
            except Exception as exc:
                logger.debug(f"Metadata extraction failed for {mp4_file}: {exc}")

            if duration is None:
                if callable(getattr(logger, "__call__", None)):
                    logger(f"Metadata unavailable for {mp4_file}, attempting MoviePy fallback")
                logger.warning(f"Falling back to MoviePy for duration of {mp4_file}")
                try:
                    with self.suppress_external_output():
                        try:
                            with VideoFileClip(str(mp4_file), audio=False, verbose=False) as video:  # type: ignore[arg-type]
                                duration = int(video.duration)
                        except TypeError:
                            with VideoFileClip(str(mp4_file), audio=False) as video:
                                duration = int(video.duration)
                except Exception as exc:
                    if callable(getattr(logger, "__call__", None)):
                        logger(f"Failed to extract duration for {mp4_file}: {exc}")
                    logger.error(f"Failed to extract duration for {mp4_file}: {exc}")
                    continue

            start_time = current_time
            end_time = current_time + duration

            timestamps.append(
                {
                    "start": f"{start_time//3600:02d}:{(start_time%3600)//60:02d}:{start_time%60:02d}",
                    "end": f"{end_time//3600:02d}:{(end_time%3600)//60:02d}:{end_time%60:02d}",
                    "title": mp4_file.stem,
                }
            )

            current_time = end_time

        video_info = {
            "timestamps": timestamps,
            "metadata": {
                "creation_date": datetime.now().isoformat(),
            },
        }

        output_path = self.output_dir / "timestamps.json"
        with open(output_path, "w") as file:
            json.dump([video_info], file, indent=2)

        return video_info

    def match_video_encoding(
        self,
        source_video_path: str,
        reference_video_path: str,
        output_filename: Optional[str] = None,
    ) -> str:
        """Re-encode source video to match the encoding parameters of the reference video."""
        source_path = Path(source_video_path)
        reference_path = Path(reference_video_path)

        if not source_path.exists():
            raise ValueError(f"Source video does not exist: {source_path}")
        if not reference_path.exists():
            raise ValueError(f"Reference video does not exist: {reference_path}")

        logger.info(
            f"Re-encoding {source_path.name} to match encoding of {reference_path.name}"
        )

        video_probe_cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,r_frame_rate,codec_name,bit_rate,pix_fmt,profile,level",
            "-of",
            "json",
            str(reference_path),
        ]
        video_result = subprocess.run(
            video_probe_cmd, capture_output=True, text=True, check=True
        )
        video_info = json.loads(video_result.stdout)
        video_stream = video_info["streams"][0]

        audio_probe_cmd = [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream=codec_name,sample_rate,channels,bit_rate",
            "-of",
            "json",
            str(reference_path),
        ]
        audio_result = subprocess.run(
            audio_probe_cmd, capture_output=True, text=True, check=True
        )
        audio_info = json.loads(audio_result.stdout)
        audio_stream = audio_info["streams"][0] if audio_info["streams"] else None

        fps_fraction = video_stream["r_frame_rate"].split("/")
        fps = float(int(fps_fraction[0]) / int(fps_fraction[1]))

        if not output_filename:
            source_stem = source_path.stem
            reference_stem = reference_path.stem
            output_filename = f"{source_stem}_reencoded_to_match_{reference_stem}.mp4"

        output_path = source_path.parent / output_filename

        cmd = [
            "ffmpeg",
            "-hwaccel",
            "auto",
            "-i",
            str(source_path),
            "-y",
        ]

        video_codec = video_stream["codec_name"]
        if video_codec == "h264":
            cmd.extend(["-c:v", "h264_videotoolbox"])
        elif video_codec == "hevc":
            cmd.extend(["-c:v", "hevc_videotoolbox"])
        else:
            cmd.extend(["-c:v", video_codec])

        cmd.extend(
            [
                "-s",
                f"{video_stream['width']}x{video_stream['height']}",
                "-r",
                str(fps),
            ]
        )

        if "bit_rate" in video_stream and video_stream["bit_rate"] != "N/A":
            bitrate_kbps = int(int(video_stream["bit_rate"]) / 1000)
            cmd.extend(
                [
                    "-b:v",
                    f"{bitrate_kbps}k",
                    "-maxrate",
                    f"{int(bitrate_kbps * 1.5)}k",
                    "-bufsize",
                    f"{int(bitrate_kbps * 2)}k",
                ]
            )

        if audio_stream:
            cmd.extend(
                [
                    "-c:a",
                    audio_stream["codec_name"],
                    "-ar",
                    audio_stream["sample_rate"],
                    "-ac",
                    str(audio_stream["channels"]),
                ]
            )
            if "bit_rate" in audio_stream and audio_stream["bit_rate"] != "N/A":
                audio_bitrate_kbps = int(int(audio_stream["bit_rate"]) / 1000)
                cmd.extend(["-b:a", f"{audio_bitrate_kbps}k"])
        else:
            cmd.extend(["-an"])

        cmd.append(str(output_path))

        logger.info(
            f"Re-encoding {source_path.name} with parameters from {reference_path.name}"
        )
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")

        try:
            subprocess.run(cmd, check=True, capture_output=True, text=True)
            logger.info(f"Successfully re-encoded video to {output_path}")
            return str(output_path)
        except subprocess.CalledProcessError as exc:
            logger.error(f"Failed to re-encode {source_path.name}")
            logger.error(f"FFmpeg command: {' '.join(cmd)}")
            logger.error(f"FFmpeg stderr: {exc.stderr}")
            raise

    def compress_video(
        self,
        input_path: str,
        output_filename: Optional[str] = None,
        codec: str = "h265",
        crf: int = 23,
        preset: str = "medium",
    ) -> str:
        """Compress an MP4 video to reduce file size while maintaining quality."""
        input_file = Path(input_path)
        if not input_file.exists():
            raise ValueError(f"Input video does not exist: {input_file}")

        logger.info(f"Compressing video: {input_file.name}")
        original_size_mb = input_file.stat().st_size / (1024 * 1024)
        logger.info(f"Original file size: {original_size_mb:.2f} MB")

        if not output_filename:
            stem = input_file.stem
            suffix = input_file.suffix
            output_filename = f"{stem}_compressed{suffix}"

        output_path = input_file.parent / output_filename

        if codec == "auto":
            try:
                test_cmd = [
                    "ffmpeg",
                    "-f",
                    "lavfi",
                    "-i",
                    "testsrc=duration=1:size=320x240:rate=1",
                    "-c:v",
                    "hevc_videotoolbox",
                    "-t",
                    "1",
                    "-f",
                    "null",
                    "-",
                ]
                subprocess.run(test_cmd, capture_output=True, check=True)
                codec = "h265"
                logger.info("Using H.265 (HEVC) codec for optimal compression")
            except subprocess.CalledProcessError:
                codec = "h264"
                logger.info("H.265 not available, using H.264 codec")

        if codec == "h265":
            video_encoder = "hevc_videotoolbox"
            fallback_encoder = "libx265"
        else:
            video_encoder = "h264_videotoolbox"
            fallback_encoder = "libx264"

        cmd = [
            "ffmpeg",
            "-i",
            str(input_file),
            "-y",
        ]

        try:
            test_cmd = [
                "ffmpeg",
                "-f",
                "lavfi",
                "-i",
                "testsrc=duration=1:size=320x240:rate=1",
                "-c:v",
                video_encoder,
                "-t",
                "1",
                "-f",
                "null",
                "-",
            ]
            subprocess.run(test_cmd, capture_output=True, check=True)

            cmd.extend(["-c:v", video_encoder])
            if codec == "h265":
                cmd.extend(
                    [
                        "-q:v",
                        str(crf),
                        "-profile:v",
                        "main",
                        "-tag:v",
                        "hvc1",
                    ]
                )
            else:
                cmd.extend(
                    [
                        "-q:v",
                        str(crf),
                        "-profile:v",
                        "high",
                    ]
                )

            logger.info(f"Using hardware encoder: {video_encoder}")
        except subprocess.CalledProcessError:
            cmd.extend(["-c:v", fallback_encoder])
            cmd.extend(["-crf", str(crf), "-preset", preset])
            if codec == "h265":
                cmd.extend(["-profile:v", "main", "-tag:v", "hvc1"])
            else:
                cmd.extend(["-profile:v", "high"])

            logger.info(f"Using software encoder: {fallback_encoder}")

        cmd.extend(
            [
                "-c:a",
                "copy",
                "-avoid_negative_ts",
                "make_zero",
                "-movflags",
                "+faststart",
            ]
        )

        cmd.extend(["-map_metadata", "-1"])
        cmd.append(str(output_path))

        logger.info(f"Compressing with codec: {codec}, CRF: {crf}, preset: {preset}")
        logger.debug(f"FFmpeg command: {' '.join(cmd)}")

        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
            compressed_size_mb = output_path.stat().st_size / (1024 * 1024)
            compression_ratio = (1 - compressed_size_mb / original_size_mb) * 100

            logger.info("Compression completed successfully!")
            logger.info(f"Original size: {original_size_mb:.2f} MB")
            logger.info(f"Compressed size: {compressed_size_mb:.2f} MB")
            logger.info(f"Size reduction: {compression_ratio:.1f}%")

            return str(output_path)
        except subprocess.CalledProcessError as exc:
            logger.error(f"Failed to compress video: {input_file.name}")
            logger.error(f"FFmpeg command: {' '.join(cmd)}")
            logger.error(f"FFmpeg stderr: {exc.stderr}")

            if output_path.exists():
                output_path.unlink()

            raise
