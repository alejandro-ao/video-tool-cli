# Bug Fixes for CLI

## Issues Fixed

### 1. Path Handling with Spaces

**Problem:** Commands failed when paths contained spaces, even when the directory existed.

**Example of the error:**
```bash
video-tool silence-removal --input-dir '/Users/alejandro/Screen\ Studio\ Projects/chatgpt-apps/test'
# Error: Invalid input directory: /Users/alejandro/Screen\ Studio\ Projects/chatgpt-apps/test
```

**Root Cause:** The `normalize_path()` function wasn't properly handling:
- Escaped spaces (`\ `) that the shell passes literally
- Proper path expansion and resolution

**Fix:** Updated `normalize_path()` to:
1. Remove surrounding quotes (both single and double)
2. Handle escaped spaces by replacing `\ ` with ` `
3. Expand user home directory (`~`)
4. Resolve to absolute path

**Updated Code:**
```python
def normalize_path(raw: str) -> str:
    """Normalize shell-style input paths (quotes / escaped spaces)."""
    trimmed = raw.strip()
    # Remove surrounding quotes if present
    if trimmed.startswith('"') and trimmed.endswith('"'):
        trimmed = trimmed[1:-1]
    elif trimmed.startswith("'") and trimmed.endswith("'"):
        trimmed = trimmed[1:-1]
    # Handle escaped spaces (shell passes these literally)
    trimmed = trimmed.replace("\\ ", " ")
    # Expand user home directory and resolve to absolute path
    return str(Path(trimmed).expanduser().resolve())
```

**Now Works With:**
- Quoted paths: `'/path/with spaces'` or `"/path/with spaces"`
- Escaped spaces: `/path/with\ spaces`
- Plain paths: `/path/with spaces`
- Home directory: `~/Documents/my folder`

---

### 2. Output Directory Argument Not Being Used

**Problem:** The `--output-dir` argument was accepted but never used. Commands always used the default `input_dir/output` directory.

**Example:**
```bash
video-tool concat --input-dir ./clips --output-dir ./custom-output
# Still created output in ./clips/output instead of ./custom-output
```

**Root Cause:**
1. `VideoProcessor` class didn't accept a custom output directory parameter
2. CLI commands weren't passing the `--output-dir` value to `VideoProcessor`

**Fix:**

**Step 1:** Updated `VideoProcessorBase.__init__()` to accept optional `output_dir`:

```python
def __init__(
    self,
    input_dir: str,
    video_title: Optional[str] = None,
    show_external_logs: bool = False,
    output_dir: Optional[str] = None,  # NEW PARAMETER
):
    self.input_dir = Path(input_dir)
    self.output_dir = Path(output_dir) if output_dir else self.input_dir / "output"
    self.output_dir.mkdir(parents=True, exist_ok=True)  # Creates if doesn't exist
    # ... rest of initialization
```

**Step 2:** Updated all CLI commands to:
1. Normalize the `--output-dir` argument if provided
2. Pass it to `VideoProcessor`

**Example from `cmd_concat()`:**
```python
def cmd_concat(args: argparse.Namespace) -> None:
    """Concatenate videos."""
    # ... input dir handling ...

    # Handle output directory
    output_dir = None
    if args.output_dir:
        output_dir = normalize_path(args.output_dir)

    # ... print status ...

    # Pass output_dir to VideoProcessor
    processor = VideoProcessor(str(input_path), output_dir=output_dir)
    output_video = processor.concatenate_videos(skip_reprocessing=skip_reprocessing)
```

**Now Works:**
```bash
# Use default output directory (input_dir/output)
video-tool concat --input-dir ./clips

# Use custom output directory
video-tool concat --input-dir ./clips --output-dir ./my-custom-output

# Output directory is created if it doesn't exist
video-tool concat --input-dir ./clips --output-dir ./new-folder
```

---

## Commands Fixed

All commands that accept paths now properly handle spaces and custom output directories:

### Commands with `--input-dir` and `--output-dir`:
- ✅ `silence-removal`
- ✅ `concat`
- ✅ `timestamps`

### Commands with `--video-path`:
- ✅ `transcript`
- ✅ `context-cards`
- ✅ `bunny-video`

### Commands with `--transcript-path`:
- ✅ `description`
- ✅ `seo`
- ✅ `linkedin`
- ✅ `twitter`

---

## Testing

### Test Path Handling

```bash
# Create a test directory with spaces
mkdir -p "/tmp/test with spaces"

# Test with various path formats
video-tool silence-removal --input-dir '/tmp/test with spaces'
video-tool silence-removal --input-dir "/tmp/test with spaces"
video-tool silence-removal --input-dir /tmp/test\ with\ spaces
```

All formats now work correctly!

### Test Custom Output Directory

```bash
# Default output (creates ./clips/output)
video-tool concat --input-dir ./clips

# Custom output directory (creates ./my-output)
video-tool concat --input-dir ./clips --output-dir ./my-output

# Custom output with spaces (creates ./my output folder)
video-tool concat --input-dir ./clips --output-dir './my output folder'
```

---

## Files Modified

1. **[video_tool/video_processor/base.py](video_tool/video_processor/base.py)**
   - Added `output_dir` parameter to `VideoProcessorBase.__init__()`
   - Updated output directory creation to use `parents=True`

2. **[video_tool/cli.py](video_tool/cli.py)**
   - Fixed `normalize_path()` to handle escaped spaces
   - Updated all command functions to:
     - Normalize input paths using `normalize_path()`
     - Handle custom output directories
     - Pass `output_dir` to `VideoProcessor`

---

## Migration Notes

### For Developers

If you have custom code that creates `VideoProcessor` instances, the signature is now:

```python
# Old (still works)
processor = VideoProcessor(input_dir)

# New (with custom output directory)
processor = VideoProcessor(input_dir, output_dir="/custom/path")
```

The change is backwards compatible - if you don't provide `output_dir`, it defaults to `input_dir/output` as before.

### For Users

No migration needed! The CLI now just works better:

- Paths with spaces work correctly
- Custom output directories work as expected
- All existing commands continue to work the same way
