# Video Processing Tool

Automate Alejandro's YouTube production workflow end to end. Given a directory of source MP4 clips, the script can clean the footage, join the clips, create chapter timestamps, transcribe the final video, and generate all supporting copy for publishing.

## Features
- **Video download** from YouTube and 1000+ sites via yt-dlp
- Silence trimming with `pydub` to tighten raw footage before assembly
- MP4 concatenation with `ffmpeg`, including optional fast-path when reprocessing is unnecessary
- Automatic chapter map (`timestamps.json`) with ISO-formatted timecode
- Whisper transcription (`transcript.vtt`) via Groq
- Markdown description and context cards derived from `prompts.yaml`
- Optional Bunny.net deployment with independent toggles for uploading the final cut, chapters, and transcript captions
- YouTube deployment with OAuth2 authentication for uploading videos, thumbnails, and captions
- Optional duration CSV export for analytics

## Requirements
- Python 3.11+
- `ffmpeg` available on the system path
- `yt-dlp` for video downloads (installed automatically)
- Environment variables:
  - `GROQ_API_KEY` (transcription via Groq Whisper Large V3 Turbo)
  - `OPENAI_API_KEY` (content generation: descriptions, context cards, timestamps)
  - *(Optional)* Bunny Stream deployment:
    - `BUNNY_LIBRARY_ID`
    - `BUNNY_ACCESS_KEY`
    - `BUNNY_COLLECTION_ID`
    - `BUNNY_CAPTION_LANGUAGE` (defaults to `en`)
    - `BUNNY_VIDEO_ID` (for metadata-only updates)
  - *(Optional)* Audio enhancement:
    - `REPLICATE_API_TOKEN` (for `enhance-audio` command)
  - *(Optional)* YouTube deployment (OAuth2, no env vars):
    - Run `video-tool config youtube-auth --client-secrets /path/to/client_secrets.json`
    - Credentials saved to `~/.config/video-tool/youtube_credentials.json`

## Installation
- Using uv (editable, best for development):
  ```bash
  uv tool install --editable .
  # ensure uv tools are on PATH
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zprofile && source ~/.zprofile
  video-tool --help
  ```
- Using pipx (recommended for users):
  ```bash
  brew install pipx
  pipx ensurepath
  pipx install .
  video-tool --help
  ```
- Using pip (global or user install):
  ```bash
  pip install .
  video-tool --help
  ```
- Install directly from GitHub (no clone):
  - Replace `<username>/<repo>` and a tag like `v0.1.0` or a commit SHA.
  ```bash
  # pipx
  pipx install "video-tool @ git+https://github.com/<username>/<repo>.git@v0.1.0"

  # uv tools
  uv tool install "video-tool @ git+https://github.com/<username>/<repo>.git@v0.1.0"

  # pip
  pip install "video-tool @ git+https://github.com/<username>/<repo>.git@v0.1.0"
  ```
  If the command is not found after install, please restart your terminal and ensure your tool bin directory is on PATH (e.g., `~/.local/bin` for uv tools, or your Python user bin on macOS like `~/Library/Python/3.11/bin`).

## Usage

### CLI Structure

```
video-tool config ...                # Configuration
video-tool pipeline ...              # Full workflow (most common)
video-tool video <command> ...       # Video processing + content generation
video-tool upload <command> ...      # Bunny.net / YouTube uploads
```

### Quick Start

1. Export the required API keys
2. Run the full pipeline:
   ```bash
   video-tool pipeline -i /path/to/clips
   ```
   Or use non-interactive mode:
   ```bash
   video-tool pipeline -i /path/to/clips --yes
   ```

### Download Videos

Download from YouTube and 1000+ supported sites:

```bash
video-tool video download --url "https://youtube.com/watch?v=..." --output-dir ./downloads
```

**Supported sites include:** YouTube, Vimeo, Twitter/X, TikTok, Instagram, Facebook, Twitch, Reddit, Dailymotion, and [1000+ more](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md).

### Commands

**Video processing:**
- `video-tool video concat` - Concatenate clips into single video
- `video-tool video timestamps` - Generate chapter timestamps
- `video-tool video transcript` - Transcribe video/audio with Groq Whisper
- `video-tool video extract-audio` - Extract audio to MP3
- `video-tool video enhance-audio` - Enhance audio quality via Replicate
- `video-tool video silence-removal` - Remove silent sections
- `video-tool video download` - Download from URL

**Content generation:**
- `video-tool video description` - Generate video description
- `video-tool video context-cards` - Generate context cards

**Upload (Bunny.net):**
- `video-tool upload bunny-video` - Upload video to Bunny.net
- `video-tool upload bunny-transcript` - Upload captions
- `video-tool upload bunny-chapters` - Upload chapters

**Upload (YouTube):**
- `video-tool upload youtube-video` - Upload video to YouTube
- `video-tool upload youtube-metadata` - Update video metadata
- `video-tool upload youtube-transcript` - Upload captions

**Configuration:**
- `video-tool config llm` - Configure LLM settings
- `video-tool config youtube-auth` - YouTube OAuth2 authentication
- `video-tool config youtube-status` - Check YouTube credentials

### Outputs

All outputs are written to an `output/` subdirectory:
- Final video: `output/<title>.mp4`
- Chapters: `output/timestamps.json`
- Transcript: `output/transcript.vtt`
- Description: `output/description.md`
- Context cards: `output/context-cards.md`

All actions are logged to `video_processor.log`.

## Additional Tools
- `VideoProcessor.extract_duration_csv()` exports `video_metadata.csv` summarizing clip lengths and creation dates across a directory tree.

## Testing
Run the automated suite to exercise the CLI and processing workflows:

```bash
pytest
```

If you prefer using `uv`, execute `uv run pytest` instead.

For outstanding improvements and roadmap items, see `todo.md`.
