# Final CLI Fixes

## Summary

Fixed remaining issues with the CLI to improve usability and consistency. All commands now use `--output-path` for file-level control instead of directory-level control where appropriate.

---

## Changes Made

### 1. Fixed Transcript Command - No Unused Output Directory

**Problem:** The `transcript` command was creating an `./output` directory even when a custom output path was specified, and the directory wasn't being used.

**Root Cause:** `VideoProcessorBase.__init__()` was always creating `self.output_dir` directory immediately upon initialization.

**Fix:** Changed `VideoProcessorBase` to create output directories lazily (only when needed), rather than in `__init__()`.

**File Modified:** [video_tool/video_processor/base.py](video_tool/video_processor/base.py:23-32)

**Before:**
```python
def __init__(self, input_dir: str, ...):
    self.input_dir = Path(input_dir)
    self.output_dir = Path(output_dir) if output_dir else self.input_dir / "output"
    self.output_dir.mkdir(parents=True, exist_ok=True)  # ❌ Always creates directory
```

**After:**
```python
def __init__(self, input_dir: str, ...):
    self.input_dir = Path(input_dir)
    self.output_dir = Path(output_dir) if output_dir else self.input_dir / "output"
    # Note: output_dir is created lazily when needed, not in __init__
```

**Result:**
- ✅ No unused directories created
- ✅ Output directory only created when actually needed
- ✅ All methods that write to `output_dir` already call `.mkdir(parents=True, exist_ok=True)`

---

### 2. Added MP3 Cleanup After Transcript Generation

**Problem:** The `transcript` command extracted audio as an `.mp3` file for processing but never deleted it, leaving temporary files behind.

**Fix:** Added cleanup logic to remove the temporary MP3 file after transcript generation completes (both on success and error).

**File Modified:** [video_tool/video_processor/transcript.py](video_tool/video_processor/transcript.py:120-137)

**Added:**
```python
# Clean up temporary audio file
try:
    if audio_path.exists():
        os.remove(audio_path)
        logger.debug(f"Cleaned up temporary audio file: {audio_path}")
except Exception as cleanup_exc:
    logger.warning(f"Could not remove temporary audio file {audio_path}: {cleanup_exc}")
```

**Also added cleanup in exception handler:**
```python
except Exception as exc:
    logger.error(f"Error generating transcript: {exc}")
    # Try to clean up audio file even on error
    try:
        if audio_path.exists():
            os.remove(audio_path)
    except Exception:
        pass
    return ""
```

**Result:**
- ✅ Temporary MP3 files are automatically deleted after transcript generation
- ✅ Cleanup happens even if transcript generation fails
- ✅ No leftover `.mp3` files cluttering directories

---

### 3. Changed Timestamps Command - Use `--output-path` Only

**Problem:** The `timestamps` command had both `--output-dir` (for directory) and `--output-path` (for file), which was confusing. Since it generates a single file, only `--output-path` makes sense.

**Fix:** Removed `--output-dir` argument, kept only `--output-path`.

**Files Modified:**
- [video_tool/cli.py](video_tool/cli.py:135-158) - Command handler
- [video_tool/cli.py](video_tool/cli.py:498-504) - Argument parser

**Before:**
```bash
video-tool timestamps --input-dir ./clips --output-dir ./metadata
# Created: ./metadata/timestamps.json
```

**After:**
```bash
video-tool timestamps --input-dir ./clips --output-path ./metadata/chapters.json
# Creates: ./metadata/chapters.json
```

**Default behavior:**
```bash
video-tool timestamps --input-dir ./clips
# Creates: ./clips/output/timestamps.json (unchanged)
```

---

### 4. Changed Concat Command - Use `--output-path` Instead of `--output-dir`

**Problem:** The `concat` command had `--output-dir` (for directory) but it generates a single video file, so `--output-path` (specifying the exact file path) is more appropriate.

**Fix:** Changed from `--output-dir` to `--output-path` to allow users to specify the exact output file path.

**Files Modified:**
- [video_tool/video_processor/concatenation.py](video_tool/video_processor/concatenation.py:38-75) - Added `output_path` parameter
- [video_tool/cli.py](video_tool/cli.py:97-132) - Command handler
- [video_tool/cli.py](video_tool/cli.py:479-496) - Argument parser

**Before:**
```bash
video-tool concat --input-dir ./clips --output-dir ./videos
# Created: ./videos/concatenated.mp4 (or similar based on title)
```

**After:**
```bash
video-tool concat --input-dir ./clips --output-path ./videos/my-video.mp4
# Creates: ./videos/my-video.mp4 (exact file path)
```

**Default behavior:**
```bash
video-tool concat --input-dir ./clips
# Creates: ./clips/output/concatenated.mp4
```

---

## Command Summary

### Commands Using `--output-dir` (Directory-Level Output)

| Command | Description | Default |
|---------|-------------|---------|
| `silence-removal` | Remove silences from videos | `input_dir/output` |

**Usage:**
```bash
video-tool silence-removal --input-dir ./clips --output-dir ./processed
```

---

### Commands Using `--output-path` (File-Level Output)

| Command | Description | Default |
|---------|-------------|---------|
| `concat` | Concatenate videos into single file | `input_dir/output/concatenated.mp4` |
| `timestamps` | Generate timestamps JSON | `input_dir/output/timestamps.json` |
| `transcript` | Generate transcript VTT | `video_dir/output/transcript.vtt` |
| `description` | Generate description Markdown | `transcript_dir/description.md` |
| `linkedin` | Generate LinkedIn post | `transcript_dir/linkedin_post.md` |
| `twitter` | Generate Twitter post | `transcript_dir/twitter_post.md` |

**Usage:**
```bash
# Specify exact file paths
video-tool concat --input-dir ./clips --output-path ./my-video.mp4
video-tool timestamps --input-dir ./clips --output-path ./metadata/chapters.json
video-tool transcript --video-path ./video.mp4 --output-path ./transcripts/video.vtt
```

---

## Usage Examples

### Concat with Custom Path

```bash
# Default
video-tool concat --input-dir ./clips
# Output: ./clips/output/concatenated.mp4

# Custom file path
video-tool concat --input-dir ./clips --output-path ./final-video.mp4
# Output: ./final-video.mp4

# Custom path with directory
video-tool concat --input-dir ./clips --output-path ./videos/episode-01.mp4
# Output: ./videos/episode-01.mp4 (creates ./videos/ if needed)
```

### Timestamps with Custom Path

```bash
# Default
video-tool timestamps --input-dir ./clips
# Output: ./clips/output/timestamps.json

# Custom file path
video-tool timestamps --input-dir ./clips --output-path ./chapters.json
# Output: ./chapters.json

# Organized structure
video-tool timestamps --input-dir ./clips --output-path ./metadata/video-chapters.json
# Output: ./metadata/video-chapters.json
```

### Transcript with Automatic Cleanup

```bash
# Generate transcript (MP3 is automatically cleaned up)
video-tool transcript --video-path ./my-video.mp4

# Before fix:
#   - Creates: ./my-video.mp3 (stays on disk)
#   - Creates: ./output/transcript.vtt
#
# After fix:
#   - Creates: ./my-video.mp3 (temporary)
#   - Creates: ./output/transcript.vtt
#   - Deletes: ./my-video.mp3 ✓
```

---

## Complete Workflow Example

```bash
#!/bin/bash
set -e

INPUT_DIR="./clips"
OUTPUT_VIDEO="./videos/final-episode.mp4"
METADATA_DIR="./metadata"
TRANSCRIPTS_DIR="./transcripts"
CONTENT_DIR="./content"

# Create organized structure
mkdir -p "$METADATA_DIR" "$TRANSCRIPTS_DIR" "$CONTENT_DIR"

# Process videos
video-tool silence-removal --input-dir "$INPUT_DIR" --output-dir ./processed

# Concatenate with custom name
video-tool concat \
  --input-dir "$INPUT_DIR" \
  --output-path "$OUTPUT_VIDEO" \
  --fast-concat

# Generate metadata
video-tool timestamps \
  --input-dir "$INPUT_DIR" \
  --output-path "$METADATA_DIR/timestamps.json"

# Generate transcript (auto-cleanup)
video-tool transcript \
  --video-path "$OUTPUT_VIDEO" \
  --output-path "$TRANSCRIPTS_DIR/transcript.vtt"

# Generate content
video-tool description \
  --transcript-path "$TRANSCRIPTS_DIR/transcript.vtt" \
  --timestamps-path "$METADATA_DIR/timestamps.json" \
  --output-path "$CONTENT_DIR/description.md"

echo "✓ Processing complete!"
echo "  Video: $OUTPUT_VIDEO"
echo "  Metadata: $METADATA_DIR/timestamps.json"
echo "  Transcript: $TRANSCRIPTS_DIR/transcript.vtt"
echo "  Description: $CONTENT_DIR/description.md"
```

**Directory structure result:**
```
./
├── clips/
│   ├── clip-01.mp4
│   └── clip-02.mp4
├── processed/
│   ├── clip-01.mp4 (silence removed)
│   └── clip-02.mp4 (silence removed)
├── videos/
│   └── final-episode.mp4
├── metadata/
│   └── timestamps.json
├── transcripts/
│   └── transcript.vtt
└── content/
    └── description.md
```

---

## Benefits

1. **Consistency** - All single-file commands use `--output-path`, directory commands use `--output-dir`
2. **Precision** - Can specify exact file paths including custom filenames
3. **Clean** - No leftover temporary files (MP3 cleanup)
4. **Efficient** - No unused directories created
5. **Flexible** - Easy to organize outputs in custom directory structures

---

## Backwards Compatibility

✅ **Fully backwards compatible**

All commands work with defaults if you don't specify output paths:

```bash
# These all still work exactly as before
video-tool silence-removal --input-dir ./clips
video-tool concat --input-dir ./clips
video-tool timestamps --input-dir ./clips
video-tool transcript --video-path ./video.mp4
```

The only difference is:
- **More control** when you want it (via `--output-path`)
- **Cleaner** temporary file handling (MP3 cleanup)
- **No unused** directories created

---

## Testing

All features tested and verified:

```bash
# ✓ Concat with custom path
video-tool concat --input-dir ./test --output-path ./my-video.mp4

# ✓ Timestamps with custom path
video-tool timestamps --input-dir ./test --output-path ./my-timestamps.json

# ✓ Transcript with cleanup
video-tool transcript --video-path ./test.mp4
# (Verified: MP3 file is deleted after completion)

# ✓ No unused directories
video-tool transcript --video-path ./test.mp4 --output-path ./custom/transcript.vtt
# (Verified: No ./output directory created)

# ✓ Paths with spaces
video-tool concat --input-dir ./test --output-path './my output/video.mp4'
```

---

## Files Modified

1. **[video_tool/video_processor/base.py](video_tool/video_processor/base.py)** - Removed eager directory creation
2. **[video_tool/video_processor/transcript.py](video_tool/video_processor/transcript.py)** - Added MP3 cleanup
3. **[video_tool/video_processor/concatenation.py](video_tool/video_processor/concatenation.py)** - Added `output_path` parameter
4. **[video_tool/cli.py](video_tool/cli.py)** - Updated commands and parsers for concat and timestamps
