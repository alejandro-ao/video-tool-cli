# Video Processing Tool Instructions

## Overview
This tool concatenates multiple MP4 videos from a directory, generates timestamps, creates transcripts, and produces video descriptions with SEO keywords. Each operation is modular and can be executed independently.

## Configuration
- Environment Variables (.env file):
  - OPENAI_API_KEY: For transcription and LLM operations

- Output Organization:
  - All output files are stored in the same directory as the input videos
  - Output video naming convention: YYYY-MM-DD_video_title.mp4

## Operations

### 1. Video Concatenation
Objective: Combine multiple MP4 videos in alphabetical order.

Requirements:
- Input Format: MP4 only
- No maximum size limit
- Original videos are preserved
- Progress indicator for concatenation process

Steps:
1. Display all MP4 videos in alphabetical order
2. Ask for user confirmation
3. Concatenate videos
4. Save as YYYY-MM-DD_video_title.mp4

### 2. Timestamp Generation
Objective: Create a JSON file with chapter information for each video segment.

Output Format (timestamps.json):
```json
[
  {
    "start": "00:00:00",
    "end": "00:05:00",
    "title": "Introduction"
  },
  {
    "start": "00:05:00",
    "end": "00:10:00",
    "title": "Section 1" # name of the file
  },
  # other chapters
]
```

Where each timestamp corresponds to the duration of the each video in the original input. For example, if the videos to concatenate are video1.mp4 (duration: 30s) and video2.mp4 (duration: 25s), the timestamps would look like this:

[
{
        "start": "00:00:00",
        "end": "00:00:30",
        "title": "video1"
      },
      {
        "start": "00:00:30",
        "end": "00:00:55",
        "title": "video2"
      }
]

### 3. Transcript Generation
Objective: Create a VTT transcript using OpenAI's Whisper API.

Steps:
1. Extract audio from concatenated video
2. Send to OpenAI Whisper API
3. Handle API failures with retry mechanism (retry after 5 seconds)
4. Save as transcript.vtt

Example API Call:
```python
from openai import OpenAI

client = OpenAI()
audio_file = open("speech.mp3", "rb")
transcript = client.audio.transcriptions.create(
    model="whisper-1",
    file=audio_file,
    response_format="vtt"
)
```

### 4. Description Generation
Objective: Create a markdown file with video description using LLM.

Inputs Required:
- GitHub repository URL
- Transcript content

Output Format (description.md):
```markdown
# Video Title

[Generated Description]

## Links
- Code from the video: [GitHub Repo URL]
- 🚀 Complete AI Engineer Bootcamp: aibootcamp.dev
- ❤️ Support: [Buy me a coffee link]
- 💬 Community: [Discord Server link]
- ✉️ Updates: [Newsletter link]

## Timestamps
00:00:00 Introduction
00:01:45 [Section Title]
[...]
```

### 5. SEO Keywords Generation
Objective: Generate SEO keywords based on video description.

Steps:
1. Read description.md content
2. Generate keywords using OpenAI API
3. Save as keywords.txt

## Error Handling
- OpenAI API failures: Implement retry mechanism
- Invalid video formats: Skip non-MP4 files
- File access errors: Log and report to user

## Logging
- Operation start/end times
- Progress updates
- Error messages
- API call status

## Cleanup
- Temporary audio files
- Intermediate processing files
- Failed operation artifacts

## Skip Options
Each operation can be skipped if already executed:
1. Check for existing output files
2. Prompt user for skip confirmation
3. Proceed to next operation if skipped