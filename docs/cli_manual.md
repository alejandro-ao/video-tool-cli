# Video Tool CLI Manual

This guide explains how to use the video processing CLI. The tool provides independent commands for each processing step, making it easy to run individual tasks or chain them together.

## Quick Start

```bash
# Show all available commands
video-tool --help

# Show help for a specific command
video-tool concat --help

# Run a command with arguments
video-tool video concat --input-dir ./clips --output-path ./output/final.mp4 --fast-concat

# Run a command with interactive prompts (omit arguments)
video-tool video concat
```

## Installation

After installing the package, the `video-tool` command becomes available:

```bash
pip install -e .
# or
uv pip install -e .
```

You can also run it directly via Python:

```bash
python main.py <command> [options]
# or
python -m video_tool.cli <command> [options]
```

## Environment Setup

Required environment variables (set in `.env` or your shell):

```bash
# For transcription (Groq Whisper Large V3 Turbo)
GROQ_API_KEY=your_groq_api_key

# For content generation (descriptions, context-cards)
OPENAI_API_KEY=your_openai_api_key

# Optional: For Bunny.net uploads
BUNNY_LIBRARY_ID=your_library_id
BUNNY_ACCESS_KEY=your_access_key
BUNNY_COLLECTION_ID=your_collection_id  # optional
BUNNY_CAPTION_LANGUAGE=en  # optional, defaults to 'en'
```

**API Usage by Command:**
| Command | Groq | OpenAI |
|---------|------|--------|
| `transcript` | Yes | No |
| `description`, `context-cards` | No | Yes |
| `timestamps` (transcript mode) | No | Yes |
| `pipeline` | Yes | Yes |

## Configuration

### Config File Location
User configuration is stored in `~/.config/video-tool/config.yaml`.

### Config File Structure
```yaml
llm:
  default:
    base_url: "https://api.openai.com/v1"
    model: "gpt-4o"
  description:  # per-command override (optional)
    model: "gpt-4o-mini"

links:  # persistent links for descriptions
  - description: "Code from this video"
    url: "https://github.com/..."
```

### First-Time Setup
On first run, you'll be prompted to configure:
1. Base URL for OpenAI-compatible API
2. Default model name

### Managing Configuration
Use `video-tool config` to manage settings:
- `--show` - view current config
- `--model`, `--base-url` - set defaults
- `--command` - configure specific command
- `--links` - manage persistent links
- `--reset` - reset to defaults

## Available Commands

### Configuration

#### `config`

Configure LLM and links settings for video-tool.

**Options:**
- `--show, -s`: Show current config
- `--command, -c TEXT`: Command to configure (e.g., description, seo)
- `--model, -m TEXT`: Set model for command
- `--base-url, -b TEXT`: Set base URL for command
- `--links, -l`: Manage persistent links
- `--reset`: Reset config to defaults

**Example:**

```bash
# Show all config (LLM + links)
video-tool config --show

# Configure default model
video-tool config --model gpt-4o

# Configure model for a specific command
video-tool config --command description --model gpt-4o-mini

# Manage persistent links (interactive)
video-tool config --links

# Reset to defaults
video-tool config --reset
```

**Persistent Links:**

Use `video-tool config --links` to interactively add/edit links that will be included in descriptions when using the `--links` flag. Links are stored in `~/.config/video-tool/config.yaml`:

```yaml
llm:
  default:
    base_url: "https://api.openai.com/v1"
    model: "gpt-4o"

links:
  - description: "🚀 Complete AI Engineer Bootcamp"
    url: "https://aibootcamp.dev"
  - description: "❤️ Buy me a coffee"
    url: "https://example.com/support"
  - description: "💬 Discord Server"
    url: "https://example.com/discord"
```

---

### Video Processing Commands

#### `download`

Download video from a URL (YouTube, etc.) using yt-dlp.

**Required inputs:**
- Video URL

**Optional inputs:**
- Output directory (prompts if not provided)
- Output filename

**Example:**

```bash
# With arguments
video-tool video download --url "https://youtube.com/watch?v=..." --output-dir ./downloads --name "my-video"

# Interactive (prompts for missing inputs)
video-tool video download
```

**Arguments:**
- `--url, -u URL`: Video URL to download
- `--output-dir, -o PATH`: Output directory
- `--name, -n TEXT`: Output filename (without extension)

---

#### `silence-removal`

Remove silences from a video file.

**Required inputs:**
- Input video file

**Optional inputs:**
- Output file path (defaults to `<input_stem>_no_silence.mp4`)
- Silence threshold in seconds (default: 1.0)

**Example:**

```bash
# With arguments
video-tool video silence-removal --input ./clip.mp4 --output-path ./clip_clean.mp4 --threshold 0.5

# Interactive (prompts for missing inputs)
video-tool video silence-removal
```

**Arguments:**
- `--input, -i PATH`: Input video file
- `--output-path, -o PATH`: Output video file path
- `--threshold, -t SECONDS`: Min silence duration in seconds to remove (default: 1.0)

---

#### `concat`

Concatenate multiple video clips into a single video.

**Required inputs:**
- Input directory (containing video files to concatenate)

**Optional inputs:**
- Output file path (.mp4)
- Fast concatenation mode (true/false)

**Example:**

```bash
# Standard concatenation
video-tool video concat --input-dir ./clips --output-path ./output/final.mp4

# Fast concatenation (skip reprocessing)
video-tool video concat --input-dir ./clips --output-path ./final.mp4 --fast-concat

# Interactive
video-tool video concat
```

**Arguments:**
- `--input-dir, -i PATH`: Input directory containing videos to concatenate
- `--output-path, -o PATH`: Full output file path (.mp4)
- `--fast-concat/-f/--no-fast-concat`: Use fast concatenation mode (skip reprocessing)

Writes a `metadata.json` file alongside the concatenated video with basic details (title, duration, file size).

---

#### `timestamps`

Generate video chapter timestamps (useful for YouTube chapters).

Two modes available:
- **clips**: One chapter per video clip in a directory. If a transcript exists (`transcript.vtt`), you'll be prompted to configure an LLM for title refinement. Leave empty to skip and use filenames as titles.
- **transcript**: LLM-analyzed chapters from a VTT transcript

**Required inputs:**
- Mode: `clips` or `transcript`
- Input: directory (clips mode) or VTT file (transcript mode)

**Optional inputs:**
- Output JSON path (defaults to `timestamps.json`)
- Granularity: low/medium/high (transcript mode only)
- Additional notes for LLM (transcript mode only)

**Example:**

```bash
# Clips mode: one chapter per clip
video-tool video timestamps --mode clips --input ./clips --output-path ./timestamps.json

# Transcript mode: LLM-generated chapters from VTT
video-tool video timestamps --mode transcript --input ./transcript.vtt --granularity medium

# Interactive (prompts for mode and inputs)
video-tool video timestamps
```

**Arguments:**
- `--mode, -m MODE`: Generation mode: `clips` or `transcript`
- `--input, -i PATH`: Input directory (clips mode) or VTT file (transcript mode)
- `--output-path, -o PATH`: Output JSON file path (default: timestamps.json)
- `--granularity, -g LEVEL`: Chapter density: `low`/`medium`/`high` (transcript mode only)
- `--notes, -n TEXT`: Additional LLM instructions (transcript mode only)

**Output:** Creates `timestamps.json` and updates `metadata.json` with timestamps.

---

#### `transcript`

Generate a VTT transcript from video or audio using Groq Whisper Large V3 Turbo.

Accepts video files (extracts audio internally) or audio files directly (skips extraction). Only requires `GROQ_API_KEY`.

**Supported formats:**
- Video: `.mp4`, `.mov`
- Audio: `.mp3`, `.wav`, `.m4a`, `.aac`, `.flac`, `.ogg`

**Required inputs:**
- Input file (video or audio)

**Optional inputs:**
- Output path (defaults to `input_dir/transcript.vtt`)
- Writes/updates `metadata.json` next to the transcript with the full transcript text

**Example:**

```bash
# From video (extracts audio, then transcribes)
video-tool video transcript --input ./my-video.mp4

# From audio (transcribes directly, no extraction)
video-tool video transcript --input ./audio.mp3

# Custom output path
video-tool video transcript -i ./video.mp4 -o ./subs/transcript.vtt

# Interactive mode
video-tool video transcript
```

**Arguments:**
- `--input, -i PATH`: Input video or audio file
- `--output-path, -o PATH`: Output VTT file path (default: input_dir/transcript.vtt)

**Output:** Creates `transcript.vtt` in the chosen output directory and updates/creates `metadata.json`.

---

#### `context-cards`

Generate context cards and resource mentions from a transcript or media file.

**Required inputs:**
- Input file (video/audio/vtt)

**Optional inputs:**
- Output path (defaults to `input_dir/context-cards.md`)
- Updates/creates `metadata.json` with the full context cards content

**Example:**

```bash
# From transcript
video-tool video context-cards --input ./output/transcript.vtt

# From video (auto-generates transcript)
video-tool video context-cards -i ./output/final.mp4

# Custom output location
video-tool video context-cards \
  -i ./output/transcript.vtt \
  -o ./output/custom-context-cards.md
```

**Arguments:**
- `--input, -i PATH`: Input file (video/audio/vtt)
- `--output, -o PATH`: Full path for the generated context cards file (default: input_dir/context-cards.md)

**Output:** Creates `context-cards.md` in the chosen output directory and updates/creates `metadata.json`.

---

#### `description`

Generate a video description from a transcript.

**Required inputs:**
- Input file (video/audio/vtt/md/txt)

**Optional inputs:**
- Output path (defaults to `input_dir/description.md`)
- Timestamps JSON path (for including chapter timestamps)
- Links flags for including links in the description
- Updates/creates `metadata.json` with the full description text

**Link Options:**

The description command supports flexible link inclusion:

| Flag | Purpose |
|------|---------|
| `--links, -l` | Include persistent links from config |
| `--code-link URL` | Video-specific link to code repository |
| `--article-link URL` | Video-specific link to written article |

Links are added in order: video-specific first (code/article), then persistent links from config.

**Example:**

```bash
# Basic usage (no links)
video-tool video description -i ./transcript.vtt

# With persistent links from config
video-tool video description -i ./transcript.vtt --links

# With video-specific code link
video-tool video description -i ./transcript.vtt --links --code-link https://github.com/user/repo

# With both video-specific links
video-tool video description -i ./transcript.vtt --links \
  --code-link https://github.com/user/repo \
  --article-link https://blog.example.com/post

# Auto-generate transcript from video
video-tool video description -i ./video.mp4 --links
```

**Arguments:**
- `--input, -i PATH`: Input file (video/audio/vtt/md/txt)
- `--output-path, -o PATH`: Full path for output description (default: input_dir/description.md)
- `--timestamps, -t PATH`: Path to timestamps JSON file
- `--links, -l`: Include persistent links from config
- `--code-link URL`: Link to code repository for this video
- `--article-link URL`: Link to written article for this video

**Output:** Creates `description.md` in the chosen output directory and updates/creates `metadata.json`.

**First-time link setup:** If `--links` is passed but no links exist in config, you'll be prompted to add them interactively.

---

#### `pipeline`

Run the full video-tool pipeline (silence removal not included) for an input directory of clips. The pipeline now collects everything up front and then runs non-interactively (no step-level prompts): input/output directories, concat title/output path, fast concat toggle, timestamps settings (granularity/notes/output), transcript output path, whether to generate context cards, and optional Bunny upload credentials/metadata path.

**Prompts for (in order):**
- Input directory and output directory (default: `<input>/output`)
- Concatenated video title, optional custom output path, and fast/standard concat
- Timestamps output path, granularity (low/medium/high), and optional notes
- Transcript output path for the concatenated video
- Whether to generate context cards
- Optional Bunny upload toggle and credentials (library/access keys and optional collection id)

**Optional inputs:**
- Override CLI binary (defaults to `video-tool` or `VIDEO_TOOL_CLI` env)

**Example:**

```bash
video-tool pipeline
video-tool pipeline --cli-bin ./venv/bin/video-tool
```

**Output:** Executes concat, timestamps, transcript, context cards, and optional Bunny upload in sequence using defaults from the individual commands.

---

### Deployment Commands

#### `bunny-upload`

Upload a video to Bunny.net CDN.

**Required inputs:**
- Path to video file (or a directory when using `--batch-dir`)
- Bunny Library ID (or set `BUNNY_LIBRARY_ID` env var)
- Bunny Access Key (or set `BUNNY_ACCESS_KEY` env var)

**Optional inputs:**
- Bunny Collection ID (or set `BUNNY_COLLECTION_ID` env var)
- Batch upload directory (`--batch-dir`) to upload every `.mp4` in a folder

**Example:**

```bash
# With environment variables set
video-tool bunny-upload --video-path ./output/final-video.mp4

# With explicit credentials
video-tool bunny-upload \
  --video-path ./output/final-video.mp4 \
  --bunny-library-id 12345 \
  --bunny-access-key your_key \
  --bunny-collection-id 67890

# Batch upload every MP4 in a directory
video-tool bunny-upload \
  --batch-dir ./output/videos \
  --bunny-library-id 12345 \
  --bunny-access-key your_key
```

**Arguments:**
- `--video-path PATH`: Path to video file to upload
- `--batch-dir PATH`: Directory containing MP4 files to upload
- `--bunny-library-id ID`: Bunny.net library ID
- `--bunny-access-key KEY`: Bunny.net access key
- `--bunny-collection-id ID`: Bunny.net collection ID (optional)

The command prints the Bunny video ID on success. Save this ID for transcript and chapter uploads.

---

#### `bunny-transcript`

Upload a caption file to an existing Bunny.net video.

**Required inputs:**
- Bunny video ID (from `bunny-upload` or an existing asset)
- Path to transcript file (.vtt)
- Bunny Library ID (or set `BUNNY_LIBRARY_ID` env var)
- Bunny Access Key (or set `BUNNY_ACCESS_KEY` env var)

**Optional inputs:**
- Caption language code (defaults to `'en'` or `BUNNY_CAPTION_LANGUAGE`)

**Example:**

```bash
video-tool bunny-transcript \
  --video-id 4ce7321f-... \
  --transcript-path ./clips/output/transcript.vtt \
  --language en
```

**Arguments:**
- `--video-id ID`: Existing Bunny.net video ID
- `--transcript-path PATH`: Path to transcript file (.vtt)
- `--language CODE`: Caption language code (default: en)
- `--bunny-library-id ID`: Bunny.net library ID
- `--bunny-access-key KEY`: Bunny.net access key

---

#### `bunny-chapters`

Upload chapter data (timestamps) to an existing Bunny.net video.

**Required inputs:**
- Bunny video ID (from `bunny-upload` or an existing asset)
- Path to chapters JSON (accepts `timestamps.json` output, a list of chapter dicts, or a single chapter dict)
- Bunny Library ID (or set `BUNNY_LIBRARY_ID` env var)
- Bunny Access Key (or set `BUNNY_ACCESS_KEY` env var)

**Example:**

```bash
video-tool bunny-chapters \
  --video-id 4ce7321f-... \
  --chapters-path ./clips/output/timestamps.json
```

**Arguments:**
- `--video-id ID`: Existing Bunny.net video ID
- `--chapters-path PATH`: Path to chapters JSON file
- `--bunny-library-id ID`: Bunny.net library ID
- `--bunny-access-key KEY`: Bunny.net access key

---

## Interactive Mode

If you omit required arguments when running a command, the tool will prompt you interactively:

```bash
$ video-tool video concat
Input directory (containing videos to concatenate): ./clips
Output file path (.mp4, defaults to input dir): ./output/final.mp4
Use fast concatenation? [y/N]: y
```

This makes it easy to use the tool without memorizing all the argument names.

## Common Workflows

### Complete Video Processing Pipeline

Process raw clips into a final video with all content:

```bash
# 1. Remove silences from a clip
video-tool video silence-removal --input ./clips/clip-01.mp4

# 2. Concatenate into final video
video-tool video concat --input-dir ./clips --output-path ./clips/output/final.mp4 --fast-concat

# 3. Generate timestamps (clips mode)
video-tool video timestamps --mode clips --input ./clips

# 4. Generate transcript (uses Groq Whisper)
video-tool video transcript --input ./clips/output/final-video.mp4

# 5. Generate context cards
video-tool video context-cards -i ./clips/output/transcript.vtt

# 6. Generate description with links
video-tool video description \
  -i ./clips/output/transcript.vtt \
  --links \
  --code-link https://github.com/user/repo

# 7. Upload to Bunny.net (video upload)
video-tool bunny-upload --video-path ./clips/output/final-video.mp4

# 10. Upload captions to Bunny.net
video-tool bunny-transcript \
  --video-id <video_id_from_step_9> \
  --transcript-path ./clips/output/transcript.vtt

# 11. Upload chapters to Bunny.net
video-tool bunny-chapters \
  --video-id <video_id_from_step_9> \
  --chapters-path ./clips/output/timestamps.json
```

### Quick Transcript Generation

Just need a transcript for an existing video or audio file:

```bash
# From video
video-tool video transcript --input ./my-video.mp4

# From audio (faster, skips extraction)
video-tool video transcript --input ./podcast.mp3
```

## Output Structure

All generated files are stored in the `output/` directory within your input directory:

```
clips/
├── clip-01.mp4
├── clip-02.mp4
├── processed/              # After silence removal
│   ├── clip-01.mp4
│   └── clip-02.mp4
└── output/                 # All generated content
    ├── final-video.mp4     # After concatenation
    ├── transcript.vtt      # Video transcript
    ├── timestamps.json     # Chapter timestamps
    ├── description.md      # Video description
    └── context-cards.md    # Context cards
```

## Logging

- Console output shows progress and results
- Detailed logs are written to `video_processor.log` in the working directory
- Error messages include helpful troubleshooting information

## Troubleshooting

### "Missing required environment variables"

Make sure you have set `OPENAI_API_KEY` and `GROQ_API_KEY` in your `.env` file or environment.

### "Invalid input directory"

Check that the path exists and is a directory. Use absolute paths or paths relative to your current working directory.

### "No video file found"

Ensure your input directory contains `.mp4` files. The tool looks for MP4 files specifically.

### Bunny.net upload failures

- Verify your `BUNNY_LIBRARY_ID` and `BUNNY_ACCESS_KEY` are correct
- Check that the video file exists and is a valid MP4
- Ensure you have network connectivity to Bunny.net

## Advanced Usage

### Input and Output Paths

Commands use different input/output patterns depending on their function:

- **Processing commands** (`silence-removal`, `concat`, `timestamps`, `transcript`): Use `--input`/`-i` for input and `--output-path`/`-o` for output file path
- **Content commands** (`description`, `context-cards`): Use `--input`/`-i` for input and `--output`/`-o` for output

Output paths default to sensible locations (usually alongside the input file) if not specified.

### Chaining Commands with Shell Scripts

Create a shell script to automate your workflow:

```bash
#!/bin/bash
set -e

INPUT_DIR="./clips"
VIDEO_TITLE="final-video"
VIDEO_PATH="$INPUT_DIR/output/${VIDEO_TITLE}.mp4"
TRANSCRIPT_PATH="$INPUT_DIR/output/transcript.vtt"
REPO_URL="https://github.com/user/repo"

echo "Starting video processing pipeline..."

video-tool video silence-removal --input "$INPUT_DIR/clip-01.mp4"
video-tool video concat --input-dir "$INPUT_DIR" --output-path "$VIDEO_PATH" --fast-concat
video-tool video timestamps --mode clips --input "$INPUT_DIR"
video-tool video transcript --input "$VIDEO_PATH"
video-tool video description -i "$TRANSCRIPT_PATH" --links --code-link "$REPO_URL"

echo "Pipeline complete!"
```

## Migration from Old CLI

The previous version had a monolithic CLI with `--manual` mode and profiles. The new version provides:

- **Simpler**: Each tool is independent with clear inputs/outputs
- **Scriptable**: Easy to chain commands together
- **Faster**: Run only what you need without configuration overhead

To migrate:

- Old: `video-tool --manual` → New: Run individual commands as needed
- Old: `video-tool --all` → New: Run commands in sequence (see workflows above)
- Old: `video-tool --concat` → New: `video-tool concat`

The old `main_old.py` file contains the legacy implementation for reference.
