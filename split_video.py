import os
import subprocess
import sys
from pathlib import Path


def split_video(input_path: str, chunk_duration_minutes: int = 10):
    input_path = Path(input_path)

    if not input_path.exists() or input_path.suffix.lower() != ".mp4":
        print("Invalid input file. Please provide a valid .mp4 file.")
        return

    output_dir = input_path.parent / f"{input_path.stem}_chunks"
    output_dir.mkdir(exist_ok=True)

    chunk_duration_seconds = chunk_duration_minutes * 60

    # Build the ffmpeg command
    command = [
        "ffmpeg",
        "-i",
        str(input_path),
        "-c",
        "copy",  # Copy codec to avoid re-encoding
        "-map",
        "0",  # Map all streams
        "-segment_time",
        str(chunk_duration_seconds),
        "-f",
        "segment",
        "-reset_timestamps",
        "1",  # Reset timestamps per segment
        str(output_dir / f"{input_path.stem}_%03d.mp4"),
    ]

    print("Running ffmpeg command:")
    print(" ".join(command))

    subprocess.run(command, check=True)
    print(f"✅ Splitting complete. Chunks saved to: {output_dir}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python split_video.py path/to/video.mp4")
    else:
        split_video(sys.argv[1])
