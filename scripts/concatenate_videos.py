#!/usr/bin/env python3
"""
Interactive Video Concatenation Script

This script uses the VideoProcessor class to concatenate multiple videos
using ffmpeg without re-encoding (assumes videos have compatible formats).

The script will interactively ask for:
- Directory containing videos to concatenate
- Output filename for the concatenated video

Usage:
    python concatenate_videos.py
"""

import sys
import os
from pathlib import Path
from datetime import datetime

# Add parent directory to path to import video_tool
sys.path.append(str(Path(__file__).parent.parent))
from video_tool.video_processor import VideoProcessor


def get_input_directory():
    """Interactively get and validate the input directory."""
    while True:
        print("\n📁 Video Concatenation Tool")
        print("=" * 30)
        
        # Get directory input
        input_dir = input("Enter the directory containing videos to concatenate: ").strip()
        
        if not input_dir:
            print("❌ Please enter a directory path.")
            continue
        
        # Remove surrounding quotes if present (handles paths with spaces)
        if (input_dir.startswith('"') and input_dir.endswith('"')) or \
           (input_dir.startswith("'") and input_dir.endswith("'")):
            input_dir = input_dir[1:-1]
            
        # Expand user path and resolve
        input_path = Path(input_dir).expanduser().resolve()
        
        if not input_path.exists():
            print(f"❌ Directory '{input_path}' does not exist.")
            continue
            
        if not input_path.is_dir():
            print(f"❌ '{input_path}' is not a directory.")
            continue
            
        # Check for MP4 files
        mp4_files = sorted([f for f in input_path.iterdir() if f.is_file() and f.suffix.lower() == '.mp4'])
        
        if not mp4_files:
            print(f"❌ No MP4 files found in '{input_path}'.")
            continue
            
        print(f"\n✅ Found {len(mp4_files)} MP4 files:")
        for i, file in enumerate(mp4_files, 1):
            print(f"  {i}. {file.name}")
            
        confirm = input(f"\nProceed with these {len(mp4_files)} files? (y/n): ").strip().lower()
        if confirm in ['y', 'yes']:
            return str(input_path)
        elif confirm in ['n', 'no']:
            continue
        else:
            print("❌ Please enter 'y' or 'n'.")


def get_output_filename():
    """Interactively get the output filename."""
    while True:
        print("\n📝 Output Configuration")
        print("=" * 25)
        
        default_name = f"{datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}_concatenated.mp4"
        print(f"Default filename: {default_name}")
        
        output_name = input("Enter output filename (or press Enter for default): ").strip()
        
        if not output_name:
            return default_name
            
        # Ensure .mp4 extension
        if not output_name.lower().endswith('.mp4'):
            output_name += '.mp4'
            
        # Check if file already exists
        if Path(output_name).exists():
            overwrite = input(f"⚠️  File '{output_name}' already exists. Overwrite? (y/n): ").strip().lower()
            if overwrite not in ['y', 'yes']:
                continue
                
        return output_name


def main():
    try:
        # Get input directory interactively
        input_dir = get_input_directory()
        
        # Get output filename interactively
        output_filename = get_output_filename()
        
        print("\n🎬 Processing Videos")
        print("=" * 20)
        print(f"Input directory: {input_dir}")
        print(f"Output filename: {output_filename}")
        print("\nStarting concatenation...")
        
        # Create VideoProcessor and concatenate
        processor = VideoProcessor(input_dir)
        output_path = processor.concatenate_videos(
            output_filename=output_filename,
            skip_reprocessing=True
        )
        
        print(f"\n✅ Successfully concatenated videos!")
        print(f"📁 Output file: {output_path}")
        print(f"📊 File size: {Path(output_path).stat().st_size / (1024*1024):.1f} MB")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Operation cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        sys.exit(1)



if __name__ == "__main__":
    main()