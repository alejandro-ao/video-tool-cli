# Video Concatenation Scripts

This directory contains utility scripts for video processing operations.

## concatenate_videos.py

An interactive script that uses the VideoProcessor class to concatenate multiple videos using ffmpeg without re-encoding (assumes videos have compatible formats).

## split_video.py

An interactive script that splits a video file at a specified timestamp into two parts using FFmpeg.

## speed_video.py

An interactive script that adjusts the playback speed of a video file by a user-specified multiplier using FFmpeg.

### Features
- **Interactive Interface**: Prompts for video file and speed multiplier
- **Flexible Speed Input**: Supports various formats (2, 1.5x, 0.5, etc.)
- **Audio Preservation**: Maintains audio pitch when adjusting speed
- **Smart Processing**: Handles videos with or without audio tracks
- **Quality Control**: Uses optimized encoding settings for good quality
- **Automatic Naming**: Generates descriptive output filenames
- **Duration Preview**: Shows estimated new video duration
- **Overwrite Protection**: Warns before overwriting existing files
- **Progress Feedback**: Shows processing status and file information

### Usage

```bash
cd scripts
python speed_video.py
```

The script will interactively prompt you for:
1. **Video file path**: Enter the path to your video file
2. **Speed multiplier**: Enter the desired speed (e.g., "2x", "1.5", "0.5")
3. **Confirmation**: Review and confirm the operation

### Speed Multiplier Formats
- **Faster**: `2`, `2x`, `1.5`, `1.25x` (speeds up video)
- **Slower**: `0.5`, `0.5x`, `0.25`, `0.75x` (slows down video)
- **Range**: 0.1x to 10x supported

### Output Files
The script generates files with descriptive names:
- `original_speed_2x.mp4` (2x faster)
- `original_speed_0.5x.mp4` (half speed)
- `original_speed_1.25x.mp4` (1.25x faster)

### Technical Details
- **Video Processing**: Uses `setpts` filter to adjust video timestamps
- **Audio Processing**: Uses `atempo` filter to preserve pitch while changing speed
- **High Speed Support**: Automatically chains multiple `atempo` filters for speeds > 2x
- **Quality Settings**: Uses H.264 encoding with CRF 23 for good quality/size balance

### Example Session
```
⚡ Video Speed Adjustment Tool
================================
Enter the path to the video file: /path/to/video.mp4
📹 Video duration: 00:05:30
🔊 Audio track detected

⚡ Speed Adjustment
--------------------
Enter speed multiplier:
  • 2 or 2x = 2x faster (double speed)
  • 1.5 or 1.5x = 1.5x faster
  • 0.5 or 0.5x = 0.5x speed (half speed)
  • 0.25 or 0.25x = 0.25x speed (quarter speed)
  Range: 0.1x to 10x

Enter speed multiplier: 2
✅ Video will be 2x faster

📊 Duration change: 00:05:30 → 00:02:45

🔄 Adjusting video speed...
📁 Input: video.mp4
⚡ Speed: 2.0x
📄 Output: video_speed_2x.mp4

🎬 Processing video...
⏳ This may take a while depending on video length and speed change...
✅ Speed adjustment completed: video_speed_2x.mp4

🎉 Video speed adjustment completed successfully!
📊 Output file: video_speed_2x.mp4 (18.5 MB)
```

### split_video.py Features
- **Interactive Interface**: Prompts for video file and split timestamp
- **Flexible Timestamp Input**: Supports MM:SS, HH:MM:SS, or seconds format
- **Fast Processing**: Uses stream copying (no re-encoding) for speed
- **Smart Validation**: Checks file existence, video duration, and timestamp validity
- **Automatic Naming**: Generates descriptive output filenames
- **Overwrite Protection**: Warns before overwriting existing files
- **Progress Feedback**: Shows file sizes and processing status

### Usage

```bash
cd scripts
python split_video.py
```

The script will interactively prompt you for:
1. **Video file path**: Enter the path to your video file
2. **Split timestamp**: Enter when to split (e.g., "1:40", "01:25:30", or "100")
3. **Confirmation**: Review and confirm the operation

### Timestamp Formats
- **MM:SS**: `1:40`, `25:30`
- **HH:MM:SS**: `1:25:30`, `02:15:45`
- **Seconds**: `100`, `1500`

### Output Files
The script generates two files with descriptive names:
- `original_part1_00-00-00_to_01-40-00.mp4` (beginning to split point)
- `original_part2_01-40-00_to_end.mp4` (split point to end)

### Example Session
```
🎬 Video Splitting Tool
=========================
Enter the path to the video file: /path/to/video.mp4
📹 Video duration: 00:05:30

⏰ Split Point
---------------
Enter timestamp in one of these formats:
  • MM:SS (e.g., 1:40, 25:30)
  • HH:MM:SS (e.g., 1:25:30)
  • Seconds (e.g., 100, 1500)
  Video duration: 00:05:30

Enter split timestamp: 2:15

🔄 Splitting video...
📁 Input: video.mp4
⏰ Split at: 00:02:15
📄 Part 1: video_part1_00-00-00_to_00-02-15.mp4
📄 Part 2: video_part2_00-02-15_to_end.mp4

🎬 Creating part 1...
✅ Part 1 created: video_part1_00-00-00_to_00-02-15.mp4

🎬 Creating part 2...
✅ Part 2 created: video_part2_00-02-15_to_end.mp4

🎉 Video split completed successfully!
📊 Output files:
  • video_part1_00-00-00_to_00-02-15.mp4 (15.2 MB)
  • video_part2_00-02-15_to_end.mp4 (22.8 MB)
```

### Prerequisites

- Python 3.7+
- FFmpeg installed and available in PATH
- Required Python packages (install with `pip install -r ../requirements.txt`)

### Usage

Simply run the script and follow the interactive prompts:

```bash
python concatenate_videos.py
```

The script will:
1. **Ask for input directory**: Enter the path to the directory containing your MP4 files
2. **Show found videos**: Display all MP4 files found in alphabetical order
3. **Confirm selection**: Ask if you want to proceed with the found videos
4. **Ask for output filename**: Enter a custom filename or use the auto-generated default
5. **Process videos**: Concatenate the videos without re-encoding

### Features

- **Interactive Interface**: User-friendly prompts guide you through the process
- **Fast Concatenation**: Uses `skip_reprocessing=True` to avoid re-encoding
- **Alphabetical Ordering**: Automatically sorts videos in alphabetical order
- **Input Validation**: Validates directory existence and checks for MP4 files
- **File Preview**: Shows all found videos before processing
- **Smart Naming**: Auto-generates timestamped filenames or accepts custom names
- **Error Handling**: Comprehensive error handling with clear messages
- **File Size Reporting**: Shows the final output file size

### Important Notes

- All input videos should have compatible formats (same codec, resolution, frame rate)
- The script assumes videos don't need re-encoding for faster processing
- If videos have different formats, consider using the VideoProcessor's `concatenate_videos()` method with `skip_reprocessing=False`

### Example Session

```
📁 Video Concatenation Tool
==============================
Enter the directory containing videos to concatenate: /Users/john/videos

✅ Found 3 MP4 files:
  1. intro.mp4
  2. main_content.mp4
  3. outro.mp4

Proceed with these 3 files? (y/n): y

📝 Output Configuration
=========================
Default filename: 2024-01-15_14-30-25_concatenated.mp4
Enter output filename (or press Enter for default): final_video.mp4

🎬 Processing Videos
====================
Input directory: /Users/john/videos
Output filename: final_video.mp4

Starting concatenation...
✅ Successfully concatenated videos!
📁 Output file: /Users/john/videos/final_video.mp4
📊 File size: 245.3 MB
```

### Error Handling

The script will:
- Validate that all specified video files exist
- Check if directories exist and are accessible
- Provide clear error messages for common issues
- Exit gracefully with appropriate error codes