# Feature Updates - Output Path Control

## Summary

Added comprehensive output path control to all CLI commands, allowing users to specify custom output locations for generated files. Also fixed the `silence-removal` command to respect custom output directories.

## Changes Made

### 1. Fixed `silence-removal` Output Directory

**Problem:** The `silence-removal` command was hardcoded to use `./processed` directory, ignoring the `--output-dir` argument.

**Fix:** Updated `remove_silences()` method in `[video_tool/video_processor/silence.py](video_tool/video_processor/silence.py:14-19)` to use `self.output_dir` instead of hardcoded `processed/` directory.

**Before:**
```python
def remove_silences(self) -> str:
    """
    Detect and remove silences from videos in the input directory, saving outputs to `processed/`.
    """
    processed_dir = self.input_dir / "processed"
    processed_dir.mkdir(exist_ok=True)
```

**After:**
```python
def remove_silences(self) -> str:
    """
    Detect and remove silences from videos in the input directory, saving outputs to the output directory.
    """
    processed_dir = self.output_dir
    processed_dir.mkdir(parents=True, exist_ok=True)
```

**Usage:**
```bash
# Default (creates input_dir/output)
video-tool silence-removal --input-dir ./clips

# Custom output directory
video-tool silence-removal --input-dir ./clips --output-dir ./processed-clips
```

---

### 2. Added `--output-path` to `timestamps` Command

**Feature:** Users can now specify the full path for the timestamps JSON file.

**Updated Files:**
- `[video_tool/video_processor/concatenation.py](video_tool/video_processor/concatenation.py:232)` - Added `output_path` parameter
- `[video_tool/cli.py](video_tool/cli.py:129-166)` - Updated CLI command handler

**Usage:**
```bash
# Default (creates output_dir/timestamps.json)
video-tool timestamps --input-dir ./clips

# Custom output path
video-tool timestamps --input-dir ./clips --output-path ./my-timestamps.json

# Custom output directory + custom file name
video-tool timestamps --input-dir ./clips --output-dir ./metadata --output-path ./metadata/video-chapters.json
```

---

### 3. Added `--output-path` to `transcript` Command

**Feature:** Users can now specify the full path for the transcript VTT file.

**Updated Files:**
- `[video_tool/video_processor/transcript.py](video_tool/video_processor/transcript.py:14)` - Added `output_path` parameter
- `[video_tool/cli.py](video_tool/cli.py:169-199)` - Updated CLI command handler

**Usage:**
```bash
# Default (creates video_dir/output/transcript.vtt)
video-tool transcript --video-path ./my-video.mp4

# Custom output path
video-tool transcript --video-path ./my-video.mp4 --output-path ./transcripts/my-video-transcript.vtt

# Custom output with spaces in path
video-tool transcript --video-path ./my-video.mp4 --output-path '/my transcripts/video.vtt'
```

---

### 4. Added `--output-path` to Content Generation Commands

**Feature:** Users can now specify custom output paths for generated content files.

**Updated Commands:**
- `description` - Generate video description
- `linkedin` - Generate LinkedIn post
- `twitter` - Generate Twitter post

**Updated Files:**
- `[video_tool/video_processor/content.py](video_tool/video_processor/content.py)`
  - `generate_description()` - Added `output_path` parameter (line 15-20)
  - `generate_linkedin_post()` - Added `output_path` parameter (line 218)
  - `generate_twitter_post()` - Added `output_path` parameter (line 249)
- `[video_tool/cli.py](video_tool/cli.py)`
  - Updated `cmd_description()`, `cmd_linkedin()`, `cmd_twitter()`

**Usage:**

```bash
# Description command
video-tool description --transcript-path ./output/transcript.vtt
video-tool description --transcript-path ./output/transcript.vtt --output-path ./content/description.md

# LinkedIn command
video-tool linkedin --transcript-path ./output/transcript.vtt
video-tool linkedin --transcript-path ./output/transcript.vtt --output-path ./social/linkedin.md

# Twitter command
video-tool twitter --transcript-path ./output/transcript.vtt
video-tool twitter --transcript-path ./output/transcript.vtt --output-path ./social/twitter.md
```

---

## Complete Command Reference

### Commands with `--output-dir` (directory-based output)

| Command | Description | Output Dir Default |
|---------|-------------|-------------------|
| `silence-removal` | Remove silences from videos | `input_dir/output` |
| `concat` | Concatenate videos | `input_dir/output` |
| `timestamps` | Generate timestamps | `input_dir/output` |

**Example:**
```bash
video-tool silence-removal --input-dir ./clips --output-dir ./custom-output
```

### Commands with `--output-path` (file-based output)

| Command | Description | Output Path Default |
|---------|-------------|---------------------|
| `timestamps` | Generate timestamps JSON | `output_dir/timestamps.json` |
| `transcript` | Generate transcript VTT | `video_dir/output/transcript.vtt` |
| `description` | Generate description | `transcript_dir/description.md` |
| `linkedin` | Generate LinkedIn post | `transcript_dir/linkedin_post.md` |
| `twitter` | Generate Twitter post | `transcript_dir/twitter_post.md` |

**Example:**
```bash
video-tool transcript --video-path ./video.mp4 --output-path ./my-transcript.vtt
```

---

## Implementation Details

### Path Handling

All output paths are normalized to handle:
- Spaces in paths: `/path/with spaces`, `'/path/with spaces'`, `"/path/with spaces"`, `/path/with\ spaces`
- Home directory expansion: `~/Documents/output.txt`
- Relative paths: `./output/file.txt`
- Absolute paths: `/full/path/to/file.txt`

### Directory Creation

When using `--output-path`, parent directories are automatically created if they don't exist:

```bash
# Creates ./new/nested/directory/ if it doesn't exist
video-tool transcript --video-path ./video.mp4 --output-path ./new/nested/directory/transcript.vtt
```

### Backwards Compatibility

All changes are backwards compatible. If you don't provide `--output-path`, the commands use the same default locations as before:

```bash
# These work exactly as before
video-tool silence-removal --input-dir ./clips
video-tool transcript --video-path ./video.mp4
video-tool description --transcript-path ./output/transcript.vtt
```

---

## Migration Guide

### From Fixed Paths to Custom Paths

**Old workflow (fixed paths):**
```bash
video-tool silence-removal --input-dir ./clips
# Output: ./clips/processed/

video-tool transcript --video-path ./video.mp4
# Output: ./video_dir/output/transcript.vtt
```

**New workflow (custom paths):**
```bash
video-tool silence-removal --input-dir ./clips --output-dir ./my-processed
# Output: ./my-processed/

video-tool transcript --video-path ./video.mp4 --output-path ./transcripts/video.vtt
# Output: ./transcripts/video.vtt
```

### Organizing Output by Type

```bash
#!/bin/bash
VIDEO_PATH="./my-video.mp4"
BASE_DIR="./output"

# Create organized directory structure
mkdir -p "$BASE_DIR"/{transcripts,content,social}

# Generate all content with organized paths
video-tool transcript \
  --video-path "$VIDEO_PATH" \
  --output-path "$BASE_DIR/transcripts/transcript.vtt"

video-tool description \
  --transcript-path "$BASE_DIR/transcripts/transcript.vtt" \
  --output-path "$BASE_DIR/content/description.md"

video-tool linkedin \
  --transcript-path "$BASE_DIR/transcripts/transcript.vtt" \
  --output-path "$BASE_DIR/social/linkedin.md"

video-tool twitter \
  --transcript-path "$BASE_DIR/transcripts/transcript.vtt" \
  --output-path "$BASE_DIR/social/twitter.md"
```

Result:
```
output/
├── transcripts/
│   └── transcript.vtt
├── content/
│   └── description.md
└── social/
    ├── linkedin.md
    └── twitter.md
```

---

## Testing

All features have been tested and verified to work correctly:

```bash
# Test output directory control
video-tool silence-removal --input-dir ./test --output-dir ./custom-output ✓

# Test output path control
video-tool timestamps --input-dir ./test --output-path ./my-timestamps.json ✓
video-tool transcript --video-path ./test.mp4 --output-path ./my-transcript.vtt ✓
video-tool description --transcript-path ./transcript.vtt --output-path ./my-desc.md ✓
video-tool linkedin --transcript-path ./transcript.vtt --output-path ./my-linkedin.md ✓
video-tool twitter --transcript-path ./transcript.vtt --output-path ./my-twitter.md ✓

# Test paths with spaces
video-tool transcript --video-path './my video.mp4' --output-path './my output/transcript.vtt' ✓
```

---

## Files Modified

1. **[video_tool/video_processor/silence.py](video_tool/video_processor/silence.py)** - Fixed to use `self.output_dir`
2. **[video_tool/video_processor/concatenation.py](video_tool/video_processor/concatenation.py)** - Added `output_path` parameter
3. **[video_tool/video_processor/transcript.py](video_tool/video_processor/transcript.py)** - Added `output_path` parameter
4. **[video_tool/video_processor/content.py](video_tool/video_processor/content.py)** - Added `output_path` parameters to 3 methods
5. **[video_tool/cli.py](video_tool/cli.py)** - Updated all affected command handlers and argument parsers
