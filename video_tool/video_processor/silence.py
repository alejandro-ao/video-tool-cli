from __future__ import annotations

import subprocess
from datetime import timedelta
from pathlib import Path
from typing import List, Tuple

from .shared import AudioSegment, detect_nonsilent, logger


class SilenceProcessingMixin:
    """Silence detection and trimming helpers."""

    def remove_silence_from_video(
        self,
        video_path: str,
        output_path: str,
        min_silence_len: int = 1000,
        silence_thresh: int = -45,
        buffer_ms: int = 250,
    ) -> str:
        """Remove silences from a single video file.

        Args:
            video_path: Path to input video file.
            output_path: Path for output video file.
            min_silence_len: Minimum silence duration in milliseconds to remove.
            silence_thresh: Silence threshold in dB.
            buffer_ms: Buffer to add around non-silent segments.

        Returns:
            Path to the output video file.
        """
        video_file = Path(video_path)
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)

        logger.info(f"Processing video: {video_file.name}")
        audio_format = video_file.suffix.lower().lstrip(".") or None
        audio = AudioSegment.from_file(str(video_file), format=audio_format)

        nonsilent_chunks: List[Tuple[int, int]] = detect_nonsilent(
            audio,
            min_silence_len=min_silence_len,
            silence_thresh=silence_thresh,
            seek_step=1,
        )

        nonsilent_chunks = [(start, end) for start, end in nonsilent_chunks]

        for idx, (start, end) in enumerate(nonsilent_chunks):
            buffered = (
                max(0, start - buffer_ms),
                min(len(audio), end + buffer_ms),
            )
            nonsilent_chunks[idx] = buffered

        if not nonsilent_chunks:
            logger.warning(f"No non-silent chunks found in {video_file.name}, copying original.")
            import shutil
            shutil.copy2(video_file, output_file)
            return str(output_file)

        last_start, last_end = nonsilent_chunks[-1]
        audio_duration_ms = len(audio)
        if last_end < audio_duration_ms:
            extension = (audio_duration_ms - last_end) / 1000
            logger.info(f"Extending last chunk to the end of the video by {extension:.2f}s.")
            nonsilent_chunks[-1] = (last_start, audio_duration_ms)

        num_silences = len(nonsilent_chunks) - 1
        total_duration = audio.duration_seconds
        total_nonsilent_duration = sum((end - start) / 1000 for start, end in nonsilent_chunks)
        silence_duration = total_duration - total_nonsilent_duration

        silence_ratio = (silence_duration / total_duration) * 100 if total_duration else 0
        logger.info(
            f"Found {num_silences} silences in {video_file.name}. "
            f"Total silence duration: {silence_duration:.2f} seconds ({silence_ratio:.1f}%)."
        )

        if len(nonsilent_chunks) > 1:
            for idx in range(len(nonsilent_chunks) - 1):
                silence_start = nonsilent_chunks[idx][1] / 1000
                silence_end = nonsilent_chunks[idx + 1][0] / 1000
                silence_length = silence_end - silence_start
                logger.info(
                    f"Silence {idx + 1}/{num_silences} in {video_file.name}: "
                    f"from {timedelta(seconds=int(silence_start))} "
                    f"to {timedelta(seconds=int(silence_end))} "
                    f"(duration: {silence_length:.2f}s)"
                )

        self._process_video_with_concat_filter(video_file, nonsilent_chunks, output_file.parent, output_file.name)

        return str(output_file)

    def remove_silences(self) -> str:
        """
        Detect and remove silences from videos in the input directory, saving outputs to the output directory.
        """
        processed_dir = self.output_dir
        processed_dir.mkdir(parents=True, exist_ok=True)

        for video_file in self.get_video_files():
            logger.info(f"Processing video: {video_file.name}")
            audio_format = video_file.suffix.lower().lstrip(".") or None
            audio = AudioSegment.from_file(str(video_file), format=audio_format)

            nonsilent_chunks: List[Tuple[int, int]] = detect_nonsilent(
                audio,
                min_silence_len=1000,
                silence_thresh=-45,
                seek_step=1,
            )

            nonsilent_chunks = [(start, end) for start, end in nonsilent_chunks]
            buffer_ms = 250

            for idx, (start, end) in enumerate(nonsilent_chunks):
                buffered = (
                    max(0, start - buffer_ms),
                    min(len(audio), end + buffer_ms),
                )
                nonsilent_chunks[idx] = buffered

            if not nonsilent_chunks:
                logger.warning(
                f"No non-silent chunks found in {video_file.name}, skipping."
                )
                continue

            last_start, last_end = nonsilent_chunks[-1]
            audio_duration_ms = len(audio)
            if last_end < audio_duration_ms:
                extension = (audio_duration_ms - last_end) / 1000
                logger.info(
                    f"Extending last chunk to the end of the video by {extension:.2f}s."
                )
                nonsilent_chunks[-1] = (
                    last_start,
                    audio_duration_ms,
                )

            num_silences = len(nonsilent_chunks) - 1
            total_duration = audio.duration_seconds
            total_nonsilent_duration = sum(
                (end - start) / 1000 for start, end in nonsilent_chunks
            )
            silence_duration = total_duration - total_nonsilent_duration

            silence_ratio = (
                (silence_duration / total_duration) * 100 if total_duration else 0
            )
            logger.info(
                f"Found {num_silences} silences in {video_file.name}. "
                f"Total silence duration: {silence_duration:.2f} seconds "
                f"({silence_ratio:.1f}%)."
            )

            if len(nonsilent_chunks) > 1:
                for idx in range(len(nonsilent_chunks) - 1):
                    silence_start = nonsilent_chunks[idx][1] / 1000
                    silence_end = nonsilent_chunks[idx + 1][0] / 1000
                    silence_length = silence_end - silence_start
                    logger.info(
                        f"Silence {idx + 1}/{num_silences} in {video_file.name}: "
                        f"from {timedelta(seconds=int(silence_start))} "
                        f"to {timedelta(seconds=int(silence_end))} "
                        f"(duration: {silence_length:.2f}s)"
                    )

            self._process_video_with_concat_filter(
                video_file, nonsilent_chunks, processed_dir
            )

        return str(processed_dir)

    def _process_video_with_concat_filter(
        self, video_file: Path, nonsilent_chunks: List[Tuple[int, int]], processed_dir: Path, output_filename: str | None = None
    ):
        """Use ffmpeg concat filters to stitch non-silent segments."""
        output_path = processed_dir / (output_filename or video_file.name)

        if not nonsilent_chunks:
            logger.warning(f"No content to process for {video_file.name}.")
            return

        filter_complex: List[str] = []
        for idx, (start, end) in enumerate(nonsilent_chunks):
            filter_complex.append(
                "[0:v]trim=start={start}:end={end},setpts=PTS-STARTPTS[v{idx}];"
                "[0:a]atrim=start={start}:end={end},asetpts=PTS-STARTPTS[a{idx}]".format(
                    start=start / 1000, end=end / 1000, idx=idx
                )
            )

        concat_video_streams = "".join(f"[v{idx}]" for idx in range(len(nonsilent_chunks)))
        concat_audio_streams = "".join(f"[a{idx}]" for idx in range(len(nonsilent_chunks)))
        filter_complex.append(
            f"{concat_video_streams}concat=n={len(nonsilent_chunks)}:v=1:a=0[outv]"
        )
        filter_complex.append(
            f"{concat_audio_streams}concat=n={len(nonsilent_chunks)}:v=0:a=1[outa]"
        )

        cmd = [
            "ffmpeg",
            "-y",
            "-i",
            str(video_file),
            "-filter_complex",
            ";".join(filter_complex),
            "-map",
            "[outv]",
            "-map",
            "[outa]",
            str(output_path),
        ]

        logger.info(f"Running ffmpeg with concat filter for {video_file.name}")
        try:
            subprocess.run(
                cmd,
                check=True,
                **self._quiet_subprocess_kwargs(),
            )
            logger.info(f"Successfully processed {video_file.name} to {output_path}")
        except subprocess.CalledProcessError as exc:
            logger.error(f"Failed to process {video_file.name} with ffmpeg.")
            logger.error(f"FFmpeg command: {' '.join(cmd)}")
            logger.error(f"FFmpeg stderr: {exc.stderr}")
            raise
