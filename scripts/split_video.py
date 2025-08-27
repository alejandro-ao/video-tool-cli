#!/usr/bin/env python3
"""
Interactive Video Splitting Script

This script splits a video file at a specified timestamp into two parts:
- Part 1: From beginning to the split point
- Part 2: From the split point to the end

Requires:
- Python 3.7+
- FFmpeg installed and accessible in PATH
"""

import subprocess
import sys
import os
import re
from pathlib import Path
from datetime import datetime


def validate_timestamp(timestamp):
    """
    Validate and normalize timestamp format.
    Accepts formats like: 1:40, 01:40, 1:40:30, 01:40:30, 90 (seconds)
    Returns normalized timestamp or None if invalid.
    """
    timestamp = timestamp.strip()
    
    # Pattern for MM:SS or HH:MM:SS format
    time_pattern = r'^(\d{1,2}):(\d{2})(?::(\d{2}))?$'
    match = re.match(time_pattern, timestamp)
    
    if match:
        hours = 0
        minutes = int(match.group(1))
        seconds = int(match.group(2))
        
        if match.group(3):  # HH:MM:SS format
            hours = minutes
            minutes = int(match.group(2))
            seconds = int(match.group(3))
        
        # Validate ranges
        if minutes >= 60 or seconds >= 60:
            return None
            
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    
    # Try parsing as pure seconds
    try:
        total_seconds = int(timestamp)
        if total_seconds < 0:
            return None
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    except ValueError:
        return None


def get_video_duration(video_path):
    """
    Get video duration using ffprobe.
    Returns duration in seconds or None if failed.
    """
    try:
        cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-show_entries', 'format=duration',
            '-of', 'csv=p=0',
            str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, ValueError):
        return None


def timestamp_to_seconds(timestamp):
    """
    Convert HH:MM:SS timestamp to total seconds.
    """
    parts = timestamp.split(':')
    hours = int(parts[0])
    minutes = int(parts[1])
    seconds = int(parts[2])
    return hours * 3600 + minutes * 60 + seconds


def get_input_file():
    """
    Interactively get and validate the input video file.
    """
    while True:
        print("\n🎬 Video Splitting Tool")
        print("=" * 25)
        
        # Get file input
        input_file = input("Enter the path to the video file: ").strip()
        
        if not input_file:
            print("❌ Please enter a file path.")
            continue
        
        # Remove surrounding quotes if present
        if (input_file.startswith('"') and input_file.endswith('"')) or \
           (input_file.startswith("'") and input_file.endswith("'")):
            input_file = input_file[1:-1]
            
        # Expand user path and resolve
        file_path = Path(input_file).expanduser().resolve()
        
        if not file_path.exists():
            print(f"❌ File '{file_path}' does not exist.")
            continue
            
        if not file_path.is_file():
            print(f"❌ '{file_path}' is not a file.")
            continue
        
        # Check if it's a video file (basic check by extension)
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v'}
        if file_path.suffix.lower() not in video_extensions:
            print(f"⚠️  Warning: '{file_path.suffix}' may not be a supported video format.")
            confirm = input("Continue anyway? (y/N): ").strip().lower()
            if confirm not in ['y', 'yes']:
                continue
        
        # Get video duration
        duration = get_video_duration(file_path)
        if duration:
            duration_str = f"{int(duration//3600):02d}:{int((duration%3600)//60):02d}:{int(duration%60):02d}"
            print(f"📹 Video duration: {duration_str}")
        else:
            print("⚠️  Could not determine video duration.")
        
        return file_path, duration


def get_split_timestamp(duration=None):
    """
    Interactively get and validate the split timestamp.
    """
    while True:
        print("\n⏰ Split Point")
        print("-" * 15)
        print("Enter timestamp in one of these formats:")
        print("  • MM:SS (e.g., 1:40, 25:30)")
        print("  • HH:MM:SS (e.g., 1:25:30)")
        print("  • Seconds (e.g., 100, 1500)")
        
        if duration:
            duration_str = f"{int(duration//3600):02d}:{int((duration%3600)//60):02d}:{int(duration%60):02d}"
            print(f"  Video duration: {duration_str}")
        
        timestamp_input = input("\nEnter split timestamp: ").strip()
        
        if not timestamp_input:
            print("❌ Please enter a timestamp.")
            continue
        
        # Validate timestamp format
        normalized_timestamp = validate_timestamp(timestamp_input)
        if not normalized_timestamp:
            print("❌ Invalid timestamp format. Please use MM:SS, HH:MM:SS, or seconds.")
            continue
        
        # Check if timestamp is within video duration
        if duration:
            split_seconds = timestamp_to_seconds(normalized_timestamp)
            if split_seconds >= duration:
                print(f"❌ Split timestamp ({normalized_timestamp}) is beyond video duration.")
                continue
            if split_seconds <= 0:
                print("❌ Split timestamp must be greater than 00:00:00.")
                continue
        
        return normalized_timestamp


def generate_output_filenames(input_path, timestamp):
    """
    Generate output filenames for the two parts.
    """
    input_path = Path(input_path)
    stem = input_path.stem
    suffix = input_path.suffix
    parent = input_path.parent
    
    # Replace colons with dashes for filename compatibility
    timestamp_safe = timestamp.replace(':', '-')
    
    part1_name = f"{stem}_part1_00-00-00_to_{timestamp_safe}{suffix}"
    part2_name = f"{stem}_part2_{timestamp_safe}_to_end{suffix}"
    
    return parent / part1_name, parent / part2_name


def split_video(input_path, timestamp, output1_path, output2_path):
    """
    Split the video using ffmpeg.
    """
    print(f"\n🔄 Splitting video...")
    print(f"📁 Input: {input_path.name}")
    print(f"⏰ Split at: {timestamp}")
    print(f"📄 Part 1: {output1_path.name}")
    print(f"📄 Part 2: {output2_path.name}")
    
    try:
        # Create part 1 (beginning to timestamp)
        print("\n🎬 Creating part 1...")
        cmd1 = [
            'ffmpeg',
            '-i', str(input_path),
            '-t', timestamp,
            '-c', 'copy',  # Copy streams without re-encoding
            '-avoid_negative_ts', 'make_zero',
            str(output1_path),
            '-y'  # Overwrite output files
        ]
        
        subprocess.run(cmd1, check=True)
        print(f"✅ Part 1 created: {output1_path.name}")
        
        # Create part 2 (timestamp to end)
        print("\n🎬 Creating part 2...")
        cmd2 = [
            'ffmpeg',
            '-i', str(input_path),
            '-ss', timestamp,
            '-c', 'copy',  # Copy streams without re-encoding
            '-avoid_negative_ts', 'make_zero',
            str(output2_path),
            '-y'  # Overwrite output files
        ]
        
        subprocess.run(cmd2, check=True)
        print(f"✅ Part 2 created: {output2_path.name}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        print(f"❌ Error during video splitting: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def main():
    """
    Main function to orchestrate the video splitting process.
    """
    try:
        # Check if ffmpeg is available
        try:
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("❌ FFmpeg is not installed or not found in PATH.")
            print("Please install FFmpeg and make sure it's accessible from the command line.")
            return
        
        # Get input file
        input_path, duration = get_input_file()
        
        # Get split timestamp
        timestamp = get_split_timestamp(duration)
        
        # Generate output filenames
        output1_path, output2_path = generate_output_filenames(input_path, timestamp)
        
        # Check for existing files
        if output1_path.exists() or output2_path.exists():
            print(f"\n⚠️  Output files already exist:")
            if output1_path.exists():
                print(f"  • {output1_path.name}")
            if output2_path.exists():
                print(f"  • {output2_path.name}")
            
            overwrite = input("Overwrite existing files? (y/N): ").strip().lower()
            if overwrite not in ['y', 'yes']:
                print("❌ Operation cancelled.")
                return
        
        # Perform the split
        success = split_video(input_path, timestamp, output1_path, output2_path)
        
        if success:
            print(f"\n🎉 Video split completed successfully!")
            print(f"📊 Output files:")
            
            # Show file sizes
            if output1_path.exists():
                size1 = output1_path.stat().st_size / (1024 * 1024)  # MB
                print(f"  • {output1_path.name} ({size1:.1f} MB)")
            
            if output2_path.exists():
                size2 = output2_path.stat().st_size / (1024 * 1024)  # MB
                print(f"  • {output2_path.name} ({size2:.1f} MB)")
        else:
            print(f"\n❌ Video splitting failed.")
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user.")
    except Exception as e:
        print(f"\n❌ An error occurred: {e}")


if __name__ == "__main__":
    main()