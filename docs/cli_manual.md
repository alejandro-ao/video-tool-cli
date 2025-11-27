# Video Tool CLI Manual

This guide explains how to use the video processing CLI. The tool provides independent commands for each processing step, making it easy to run individual tasks or chain them together.

## Quick Start

```bash
# Show all available commands
video-tool --help

# Show help for a specific command
video-tool concat --help

# Run a command with arguments
video-tool concat --input-dir ./clips --fast-concat

# Run a command with interactive prompts (omit arguments)
video-tool concat
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
OPENAI_API_KEY=your_openai_api_key
GROQ_API_KEY=your_groq_api_key

# Optional: For Bunny.net uploads
BUNNY_LIBRARY_ID=your_library_id
BUNNY_ACCESS_KEY=your_access_key
BUNNY_COLLECTION_ID=your_collection_id  # optional
BUNNY_CAPTION_LANGUAGE=en  # optional, defaults to 'en'
```

## Available Commands

### Video Processing Commands

#### `silence-removal`

Remove silences from video clips.

**Required inputs:**
- Input directory (containing video files)

**Optional inputs:**
- Output directory (defaults to `input_dir/output`)

**Example:**

```bash
# With arguments
video-tool silence-removal --input-dir ./clips

# Interactive (prompts for missing inputs)
video-tool silence-removal
```

**Arguments:**
- `--input-dir PATH`: Input directory containing videos
- `--output-dir PATH`: Output directory (default: input_dir/output)

---

#### `concat`

Concatenate multiple video clips into a single video.

**Required inputs:**
- Input directory (containing video files to concatenate)
- Title for the final video (used to name the output file)

**Optional inputs:**
- Output path (defaults to `input_dir/output/<title>.mp4`)
- Fast concatenation mode (true/false)

**Example:**

```bash
# Standard concatenation
video-tool concat --input-dir ./clips --title "Demo Reel"

# Fast concatenation (skip reprocessing)
video-tool concat --input-dir ./clips --fast-concat --title "Demo Reel"

# Interactive
video-tool concat
```

**Arguments:**
- `--input-dir PATH`: Input directory containing videos to concatenate
- `--title TEXT`: Title for the final video (required; also used for filename)
- `--output-path PATH`: Full path for the output file (defaults to `input_dir/output/<title>.mp4`)
- `--fast-concat`: Use fast concatenation mode (skip reprocessing)
- Writes a `<output_name>_metadata.json` file alongside the concatenated video with basic details (title, duration, file size)

---

#### `timestamps`

Generate timestamp information for videos (useful for YouTube chapters).

**Required inputs:**
- Input directory (containing video files) **or** a single MP4 video path

**Optional inputs:**
- Output directory (defaults to `input_dir/output`)
- Transcript-driven chapters: `--stamps-from-transcript [PATH]` (provide a transcript path or omit the path to auto-generate one)
- Granularity selection (low/medium/high)
- Additional timestamp instructions specific to the video

**Example:**

```bash
# Directory: prompt whether to use one chapter per clip
video-tool timestamps --input-dir ./clips
# Generate chapters from an existing transcript
video-tool timestamps --input-dir ./clips --stamps-from-transcript ./clips/output/transcript.vtt
# Single video: will prompt for (or auto-generate) transcript
video-tool timestamps --input-dir ./clips/output/concatenated.mp4
```

**Arguments:**
- `--input-dir PATH`: Input directory containing videos or a single MP4 video path
- `--output-dir PATH`: Output directory (default: input_dir/output)
- `--stamps-from-transcript [PATH]`: Generate timestamps directly from a transcript (optionally supply the transcript path; leave blank to auto-generate)
- `--granularity {low|medium|high}`: Control how fine-grained the generated chapters should be
- `--timestamp-notes TEXT`: Extra instructions to guide chapter generation for this video

**Output:** Creates `timestamps.json` in the output directory.

---

#### `transcript`

Generate a transcript for a video using Groq Whisper.

**Required inputs:**
- Path to video file

**Example:**

```bash
video-tool transcript --video-path ./my-video.mp4
```

**Arguments:**
- `--video-path PATH`: Path to video file

**Output:** Creates `transcript.vtt` in the video's parent output directory.

---

### Content Generation Commands

#### `context-cards`

Generate context cards and resource mentions from a transcript.

**Required inputs:**
- Path to transcript file (.vtt)

**Example:**

```bash
video-tool context-cards --input-transcript ./output/transcript.vtt

# Custom output location
video-tool context-cards \
  --input-transcript ./output/transcript.vtt \
  --output-path ./output/custom-context-cards.md
```

**Arguments:**
- `--input-transcript PATH`: Path to transcript file (.vtt)
- `--output-path PATH`: Full path for the generated context cards file (optional)

**Note:** The transcript must already exist; generate it first using the `transcript` command.

**Output:** Creates `context-cards.md` in the output directory.

---

#### `description`

Generate a video description from a transcript.

**Required inputs:**
- Path to video transcript (.vtt file)

**Optional inputs:**
- Repository URL (for including code links)

**Example:**

```bash
video-tool description --transcript-path ./output/transcript.vtt --repo-url https://github.com/user/repo
```

**Arguments:**
- `--transcript-path PATH`: Path to video transcript (.vtt file)
- `--repo-url URL`: Repository URL to include in description (optional)

**Output:** Creates `description.md` in the output directory.

---

#### `seo`

Generate SEO keywords from a transcript.

**Required inputs:**
- Path to video transcript (.vtt file)

**Example:**

```bash
video-tool seo --transcript-path ./output/transcript.vtt
```

**Arguments:**
- `--transcript-path PATH`: Path to video transcript (.vtt file)

**Note:** If a description doesn't exist, it will be generated automatically.

**Output:** Creates `keywords.txt` in the output directory.

---

#### `linkedin`

Generate a LinkedIn post from a video transcript.

**Required inputs:**
- Path to video transcript (.vtt file)

**Example:**

```bash
video-tool linkedin --transcript-path ./output/transcript.vtt
```

**Arguments:**
- `--transcript-path PATH`: Path to video transcript (.vtt file)

**Output:** Creates `linkedin_post.md` in the output directory.

---

#### `twitter`

Generate a Twitter/X post from a video transcript.

**Required inputs:**
- Path to video transcript (.vtt file)

**Example:**

```bash
video-tool twitter --transcript-path ./output/transcript.vtt
```

**Arguments:**
- `--transcript-path PATH`: Path to video transcript (.vtt file)

**Output:** Creates `twitter_post.md` in the output directory.

---

#### `thumbnail`

Generate a thumbnail image for the video using OpenAI's GPT image generation endpoint.

**Required inputs:**
- Thumbnail description (used as the prompt)

**Optional inputs:**
- Input directory (defaults to the current working directory)
- Output directory or explicit output path
- Image size (e.g. `1280x720`, defaults to `1280x720`)
- OpenAI image model (defaults to `gpt-5`)
- Note: OpenAI's image tool currently accepts `1024x1024`, `1536x1024`, `1024x1536`, or `auto`; other dimensions are mapped to the closest supported option.

**Example:**

```bash
# Non-interactive usage
video-tool thumbnail --prompt "Bold text about AI agent demo" --size 1280x720

# Save to a specific location
video-tool thumbnail --prompt "Minimalist neon gradient" --output-path ./assets/thumbnail.png
```

**Output:** Creates `thumbnail.png` in the output directory (or at the specified path).

---

### Deployment Commands

#### `bunny-video`

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
video-tool bunny-video --video-path ./output/final-video.mp4

# With explicit credentials
video-tool bunny-video \
  --video-path ./output/final-video.mp4 \
  --bunny-library-id 12345 \
  --bunny-access-key your_key \
  --bunny-collection-id 67890

# Batch upload every MP4 in a directory
video-tool bunny-video \
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
- Bunny video ID (from `bunny-video` or an existing asset)
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
- Bunny video ID (from `bunny-video` or an existing asset)
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
$ video-tool concat
Input directory (containing videos to concatenate): ./clips
Title for the final video: Demo Reel
```

This makes it easy to use the tool without memorizing all the argument names.

## Common Workflows

### Complete Video Processing Pipeline

Process raw clips into a final video with all content:

```bash
# 1. Remove silences from clips
video-tool silence-removal --input-dir ./clips

# 2. Concatenate into final video
video-tool concat --input-dir ./clips --fast-concat --title "Project Demo"

# 3. Generate timestamps
video-tool timestamps --input-dir ./clips

# 4. Generate transcript
video-tool transcript --video-path ./clips/output/final-video.mp4

# 5. Generate context cards
video-tool context-cards --input-transcript ./clips/output/transcript.vtt

# 6. Generate description
video-tool description \
  --transcript-path ./clips/output/transcript.vtt \
  --repo-url https://github.com/user/repo

# 7. Generate SEO keywords
video-tool seo --transcript-path ./clips/output/transcript.vtt

# 8. Generate social media posts
video-tool linkedin --transcript-path ./clips/output/transcript.vtt
video-tool twitter --transcript-path ./clips/output/transcript.vtt

# 9. Upload to Bunny.net (video upload)
video-tool bunny-video --video-path ./clips/output/final-video.mp4

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

Just need a transcript for an existing video:

```bash
video-tool transcript --video-path ./my-video.mp4
```

### Social Media Content Only

Generate social media posts from an existing transcript:

```bash
video-tool linkedin --transcript-path ./transcript.vtt
video-tool twitter --transcript-path ./transcript.vtt
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
    ├── context-cards.md    # Context cards
    ├── description.md      # Video description
    ├── keywords.txt        # SEO keywords
    ├── linkedin_post.md    # LinkedIn post
    └── twitter_post.md     # Twitter post
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

### Using Different Input/Output Directories

Each command that processes files from a directory follows the pattern:

```bash
video-tool <command> --input-dir ./source --output-dir ./destination
```

The output directory defaults to `input_dir/output` if not specified.

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

video-tool silence-removal --input-dir "$INPUT_DIR"
video-tool concat --input-dir "$INPUT_DIR" --fast-concat --title "$VIDEO_TITLE"
video-tool timestamps --input-dir "$INPUT_DIR"
video-tool transcript --video-path "$VIDEO_PATH"
video-tool description --transcript-path "$TRANSCRIPT_PATH" --repo-url "$REPO_URL"
video-tool seo --transcript-path "$TRANSCRIPT_PATH"
video-tool linkedin --transcript-path "$TRANSCRIPT_PATH"
video-tool twitter --transcript-path "$TRANSCRIPT_PATH"

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
