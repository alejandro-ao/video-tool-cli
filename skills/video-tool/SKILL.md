---
name: video-tool
description: |
  Video processing toolkit. Use when user wants to:
  - Download videos from YouTube or other sites
  - Remove silence from videos
  - Trim, cut, or extract segments from videos
  - Extract audio from video files
  - Enhance or denoise audio
  - Replace audio track in a video
  - Change video playback speed
  - Concatenate multiple videos
  - Generate transcripts/captions (VTT)
  - Generate video descriptions, timestamps, or context cards
  - Upload videos to YouTube or Bunny.net CDN
  - Get video metadata (duration, resolution, codec)
allowed-tools: Bash(which:*), Bash(curl:*), Bash(uv:*), Bash(video-tool:*)
---

# Video Tool CLI

AI-powered video processing toolkit with ffmpeg operations, Whisper transcription, and content generation.

## Installation Status

video-tool: !`which video-tool > /dev/null && echo "INSTALLED" || echo "NOT INSTALLED - run installation below"`
uv: !`which uv > /dev/null && echo "INSTALLED" || echo "NOT INSTALLED"`

If video-tool is not installed, run the installation commands below before proceeding.

## Installation

```bash
# Install uv first (if not installed)
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install video-tool
uv tool install git+https://github.com/alejandro-ao/video-tool-cli.git
```

### Dependencies
- **ffmpeg**: Required for all video operations (`brew install ffmpeg` on macOS)
- **yt-dlp**: Required for video downloads (`brew install yt-dlp` on macOS)

### API Keys Setup

Configure API keys using interactive setup:

```bash
video-tool config keys
```

This prompts for:
- **Groq API key** - Required for transcription (Whisper)
- **OpenAI API key** - Required for content generation (descriptions, timestamps)
- **Bunny.net credentials** - Optional, for CDN uploads
- **Replicate API token** - Optional, for audio enhancement

Keys are stored securely in `~/.config/video-tool/credentials.yaml`.

```bash
video-tool config keys --show   # View configured keys (masked)
video-tool config keys --reset  # Clear all credentials
```

### YouTube Authentication

For YouTube uploads, run OAuth2 setup:
```bash
video-tool config youtube-auth
```

---

## Command Reference

### Video Processing

#### Download Video
Download from YouTube or other supported sites.
```bash
video-tool video download -u "URL" -o ./output -n "filename"
```
| Option | Description |
|--------|-------------|
| `-u, --url` | Video URL |
| `-o, --output-dir` | Output directory |
| `-n, --name` | Output filename (without extension) |

#### Get Video Info
Get metadata: duration, resolution, codec, bitrate.
```bash
video-tool video info -i video.mp4
```

#### Remove Silence
Remove silent segments from video.
```bash
video-tool video silence-removal -i input.mp4 -o output.mp4 -t 1.0
```
| Option | Description |
|--------|-------------|
| `-i, --input` | Input video |
| `-o, --output-path` | Output path |
| `-t, --threshold` | Min silence duration to remove (default: 1.0s) |

#### Trim Video
Cut from start and/or end of video.
```bash
video-tool video trim -i input.mp4 -o output.mp4 -s 00:00:10 -e 00:05:00
```
| Option | Description |
|--------|-------------|
| `-s, --start` | Start timestamp (HH:MM:SS, MM:SS, or seconds) |
| `-e, --end` | End timestamp |
| `-g, --gpu` | Use GPU acceleration |

#### Extract Segment
Keep only a specific portion of video.
```bash
video-tool video extract-segment -i input.mp4 -o output.mp4 -s 00:01:00 -e 00:02:30
```

#### Cut Segment
Remove a middle portion from video.
```bash
video-tool video cut -i input.mp4 -o output.mp4 -f 00:01:00 -t 00:02:00
```
| Option | Description |
|--------|-------------|
| `-f, --from` | Start of segment to remove |
| `-t, --to` | End of segment to remove |

#### Change Speed
Speed up or slow down video.
```bash
video-tool video speed -i input.mp4 -o output.mp4 -f 1.5
```
| Option | Description |
|--------|-------------|
| `-f, --factor` | Speed factor (0.25-4.0). 2.0=double, 0.5=half |
| `-p, --preserve-pitch` | Keep original audio pitch (default: yes) |

#### Concatenate Videos
Join multiple videos into one.
```bash
video-tool video concat -i ./clips/ -o ./output/final.mp4 -f
```
| Option | Description |
|--------|-------------|
| `-i, --input-dir` | Directory containing videos |
| `-o, --output-path` | Output file path |
| `-f, --fast-concat` | Skip re-encoding (faster, requires same codec) |

### Audio Operations

#### Extract Audio
Extract audio track to MP3.
```bash
video-tool video extract-audio -i video.mp4 -o audio.mp3
```

#### Enhance Audio
Improve audio quality using Resemble AI (requires Replicate API token).
```bash
video-tool video enhance-audio -i input.mp4 -o enhanced.mp4
video-tool video enhance-audio -i input.mp4 -o denoised.mp4 -d  # denoise only
```

#### Replace Audio
Swap audio track in a video.
```bash
video-tool video replace-audio -v video.mp4 -a new_audio.mp3 -o output.mp4
```

### Transcription & Content Generation

#### Generate Transcript
Create VTT captions using Groq Whisper (requires Groq API key).
```bash
video-tool video transcript -i video.mp4 -o transcript.vtt
```

#### Generate Timestamps
Create chapter markers (requires OpenAI API key for transcript mode).
```bash
# From video clips directory
video-tool video timestamps -m clips -i ./clips/ -o timestamps.json

# From transcript
video-tool video timestamps -m transcript -i transcript.vtt -o timestamps.json -g medium
```
| Option | Description |
|--------|-------------|
| `-m, --mode` | `clips` or `transcript` |
| `-g, --granularity` | `low`, `medium`, `high` (transcript mode) |
| `-n, --notes` | Additional instructions for LLM |

#### Generate Description
Create video description with optional links (requires OpenAI API key).
```bash
video-tool video description -i transcript.vtt -o description.md -t timestamps.json -l
```
| Option | Description |
|--------|-------------|
| `-t, --timestamps` | Include chapter timestamps |
| `-l, --links` | Include persistent links from config |
| `--code-link` | Link to code repository |
| `--article-link` | Link to article |

#### Generate Context Cards
Create info cards from content.
```bash
video-tool video context-cards -i transcript.vtt -o cards.json
```

### Uploads

#### YouTube Upload
Upload video as draft (requires OAuth2 auth via `video-tool config youtube-auth`).
```bash
video-tool upload youtube-video -i video.mp4 -t "Title" -d "Description" -p private
video-tool upload youtube-video -i video.mp4 --metadata-path metadata.json
```
| Option | Description |
|--------|-------------|
| `-t, --title` | Video title |
| `-d, --description` | Description text |
| `--description-file` | Read description from file |
| `--tags` | Comma-separated tags |
| `--tags-file` | Tags from file (one per line) |
| `-c, --category` | YouTube category ID (default: 27 Education) |
| `-p, --privacy` | `private` (draft) or `unlisted` only |
| `--thumbnail` | Thumbnail image path |

#### YouTube Metadata Update
Update existing video metadata.
```bash
video-tool upload youtube-metadata -v VIDEO_ID --description-file description.md
```

#### YouTube Transcript Upload
Add captions to YouTube video.
```bash
video-tool upload youtube-transcript -v VIDEO_ID -t transcript.vtt -l en
```

#### Bunny.net Uploads
Upload to Bunny.net CDN (requires Bunny credentials via `config keys`).
```bash
video-tool upload bunny-video -v video.mp4
video-tool upload bunny-transcript -v VIDEO_ID -t transcript.vtt
video-tool upload bunny-chapters -v VIDEO_ID -c timestamps.json
```

### Full Pipeline

Run complete workflow: concat → timestamps → transcript → content → optional upload.
```bash
video-tool pipeline -i ./clips/ -o ./output/ -t "Video Title" -y
```
| Option | Description |
|--------|-------------|
| `-f, --fast-concat` | Fast concatenation |
| `--timestamps-from-clips` | Generate timestamps from clip names |
| `-g, --granularity` | Timestamp detail level |
| `--upload-bunny` | Upload to Bunny.net after processing |
| `-y, --yes` | Non-interactive mode |

### Configuration

```bash
video-tool config keys             # Configure API keys (interactive setup)
video-tool config keys --show      # View configured keys
video-tool config llm              # Configure LLM settings and persistent links
video-tool config youtube-auth     # Set up YouTube OAuth2
video-tool config youtube-status   # Check YouTube credentials
```

---

## Common Workflows

See [workflows.md](workflows.md) for detailed examples.
