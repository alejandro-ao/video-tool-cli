# Video Processing Tool

Automate common YouTube production tasks with independent CLI commands. The tool can clean footage, join clips, create chapter timestamps, transcribe video/audio, generate publishing copy, and upload assets.

## Features
- **Video download** from YouTube and 1000+ sites via yt-dlp
- Silence trimming with `pydub` to tighten raw footage before assembly
- MP4 concatenation with `ffmpeg`, including optional fast-path when reprocessing is unnecessary
- Automatic chapter map (`timestamps.json`) with ISO-formatted timecode
- Local or remote transcription (`transcript.vtt`) via Parakeet, Whisper, or Groq
- Markdown description and context cards derived from `prompts.yaml`
- Optional Bunny.net deployment with independent toggles for uploading the final cut, chapters, and transcript captions
- YouTube deployment with OAuth2 authentication for uploading videos, thumbnails, and captions
- Optional duration CSV export for analytics

## Requirements
- Python 3.11+
- `ffmpeg` available on the system path
- `yt-dlp` for video downloads (installed automatically)
- API keys (configured via `video-tool config keys`):
  - *(Optional)* Groq API key (remote transcription; local models need no API key)
  - OpenAI API key (content generation: descriptions, context cards, timestamps)
  - *(Optional)* Bunny.net credentials (library ID, access key, collection ID)
  - *(Optional)* Replicate API token (audio enhancement)
  - *(Optional)* YouTube: Run `video-tool config youtube-auth` (OAuth2)

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
  ```bash
  # uv tools (recommended)
  uv tool install git+https://github.com/alejandro-ao/video-tool-cli.git

  # pipx
  pipx install git+https://github.com/alejandro-ao/video-tool-cli.git

  # pip
  pip install git+https://github.com/alejandro-ao/video-tool-cli.git
  ```
  If the command is not found after install, please restart your terminal and ensure your tool bin directory is on PATH (e.g., `~/.local/bin` for uv tools, or your Python user bin on macOS like `~/Library/Python/3.11/bin`).

## Usage

### CLI Structure

```
video-tool config ...                # Configuration
video-tool video <command> ...       # Video processing commands
video-tool generate <command> ...    # Transcripts and AI content generation
video-tool upload <command> ...      # Bunny.net / YouTube uploads
```

### Quick Start

1. Configure API keys:
   ```bash
   video-tool config keys
   ```

2. Run the commands you need, for example:
   ```bash
   video-tool video concat -i /path/to/clips -o ./output/final.mp4 --fast-concat
   video-tool generate transcript -i ./output/final.mp4 -o ./output/transcript.vtt
   video-tool video timestamps -m transcript -i ./output/transcript.vtt -o ./output/timestamps.json
   video-tool generate description -i ./output/transcript.vtt -t ./output/timestamps.json -o ./output/description.md
   ```

### Output paths

Explicit relative output paths follow normal shell conventions and resolve from the current working directory. Absolute paths are used unchanged. When `-o` is omitted, processing commands keep their default output beside the input (or in the command's documented default directory).

```bash
# Writes $PWD/output/transcript.vtt, even when the input is elsewhere
video-tool generate transcript -i /videos/final.mp4 -o ./output/transcript.vtt

# With no -o, writes /videos/transcript.vtt
video-tool generate transcript -i /videos/final.mp4
```

> **Behavior change:** older versions resolved explicit relative output paths from the input directory. Scripts relying on that behavior should pass an absolute output path or omit `-o` to retain input-relative defaults.

### Local transcription models

The tool selects an installed backend automatically. Inspect recommendations and supported models with:

```bash
video-tool config transcription --recommend
video-tool config transcription --list-models
```

Apple Silicon users can install MLX Parakeet and Whisper support:

```bash
pip install 'video-tool[transcription-mlx]'
video-tool generate transcript -i video.mp4 -m mlx/parakeet-tdt-0.6b-v2
```

For portable local Whisper use `transcription-faster-whisper`; standard Transformers and NVIDIA NeMo are available through `transcription-transformers` and `transcription-nemo`. Models download on first use and remain in their runtime cache. Parakeet 0.6B V2 is English-only; choose MLX or faster-whisper for multilingual audio. Groq remains available with `--model groq/whisper-large-v3-turbo`.

### Download Videos

Download from YouTube and 1000+ supported sites:

```bash
video-tool video download --url "https://youtube.com/watch?v=..." --output-path ./downloads/my-video.mp4
```

Note: In zsh, wrap URLs with `?` or `&` in quotes (or prefix with `noglob`) to avoid shell globbing errors.

**Supported sites include:** YouTube, Vimeo, Twitter/X, TikTok, Instagram, Facebook, Twitch, Reddit, Dailymotion, and [1000+ more](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md).

### Commands

**Video processing:**
- `video-tool video concat` - Concatenate clips into single video
- `video-tool video timestamps` - Generate chapter timestamps
- `video-tool video extract-audio` - Extract audio to MP3
- `video-tool video enhance-audio` - Enhance audio quality via Replicate
- `video-tool video silence-removal` - Remove silent sections
- `video-tool video download` - Download from URL

**Content generation:**
- `video-tool generate transcript` - Transcribe with an automatically selected local model or Groq
- `video-tool generate description` - Generate video description
- `video-tool generate context-cards` - Generate context cards

**Upload (Bunny.net):**
- `video-tool upload bunny-video` - Upload video to Bunny.net
- `video-tool upload bunny-transcript` - Upload captions
- `video-tool upload bunny-chapters` - Upload chapters

**Upload (YouTube):**
- `video-tool upload youtube-video` - Upload video to YouTube
- `video-tool upload youtube-metadata` - Update video metadata
- `video-tool upload youtube-transcript` - Upload captions

**Configuration:**
- `video-tool config keys` - Manage API keys (interactive setup, show, reset)
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

## Claude Code Skill

This tool is available as a [Claude Code](https://claude.ai/code) skill. Skills extend Claude's capabilities with specialized tools—once installed, you can ask Claude to perform video tasks in natural language.

### What You Can Ask Claude To Do

**Video Processing:**
- Download videos from YouTube and 1000+ sites
- Remove silence, trim, cut, or extract segments
- Concatenate multiple videos
- Extract audio to MP3, enhance/denoise audio
- Change playback speed, get video metadata

**Transcription & Timestamps:**
- Generate VTT transcripts with local Parakeet/Whisper or remote Groq
- Create chapter timestamps from transcript or clip names

**Content Generation:**
- Generate descriptions, SEO keywords, social posts
- Create context cards for video segments

**Uploads:**
- Upload to YouTube (private/unlisted) with metadata and captions
- Upload to Bunny.net CDN (video, transcript, chapters)

**Workflow orchestration:**
- Chain the individual commands you need for your production process.

### Example Prompts

```
"Download this YouTube video and transcribe it"
"Remove silence from video.mp4 and upload to Bunny"
"Generate a description and timestamps for this video"
```

### Installation

**From marketplace:**
```bash
/plugin marketplace add alejandro-ao/skills
/plugin install video-tool@alejandro-ao-skills
```

**Direct from this repo:**
```bash
/install-skill https://github.com/alejandro-ao/video-tool-cli
```

The skill definition lives in `skills/video-tool/`.

## Additional Tools
- `VideoProcessor.extract_duration_csv()` exports `video_metadata.csv` summarizing clip lengths and creation dates across a directory tree.

## Testing
Run the automated suite to exercise the CLI and processing workflows:

```bash
pytest
```

If you prefer using `uv`, execute `uv run pytest` instead.

For outstanding improvements and roadmap items, see `todo.md`.
