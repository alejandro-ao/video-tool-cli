# CLI Refactoring Summary

## Overview

The video-tool CLI has been refactored to make each tool independently callable with cleaner argument handling. This makes the tool more modular, scriptable, and easier to maintain.

## Key Changes

### 1. New Command Structure

**Before:**
```bash
video-tool --manual  # Interactive mode
video-tool --all --input-dir ./clips  # Run everything
video-tool --concat --input-dir ./clips  # Run single step with prefix
```

**After:**
```bash
video-tool concat --input-dir ./clips  # Run single tool
video-tool transcript --video-path ./video.mp4  # Each tool has clear inputs
video-tool silence-removal  # Interactive prompts for missing args
```

### 2. Independent Tools

Each tool is now a standalone command with its own arguments:

- `silence-removal` - Remove silences from videos
- `concat` - Concatenate videos
- `timestamps` - Generate timestamps
- `transcript` - Generate transcript
- `context-cards` - Generate context cards
- `description` - Generate video description
- `seo` - Generate SEO keywords
- `linkedin` - Generate LinkedIn post
- `twitter` - Generate Twitter post
- `bunny-video` - Upload to Bunny.net

### 3. Interactive Argument Prompting

If you omit required arguments, the tool prompts for them:

```bash
$ video-tool concat
Input directory (containing videos to concatenate): ./clips
```

This makes the tool easy to use both interactively and in scripts.

### 4. Simplified File Structure

**New files:**
- `video_tool/cli.py` - New modular CLI implementation
- `main.py` - Simplified entry point (backwards compatible)
- `main_old.py` - Original implementation (kept for reference)

**Modified files:**
- `pyproject.toml` - Added `video-tool` console script entry point
- `docs/cli_manual.md` - Updated documentation with new command structure

## Benefits

1. **Simpler**: Each tool has clear inputs and outputs
2. **More maintainable**: Each command is independent, easier to test and modify
3. **Scriptable**: Easy to chain commands in shell scripts or automation
4. **Flexible**: Run only what you need, when you need it
5. **Better UX**: Interactive prompts make the tool approachable

## Migration Guide

### Running Individual Tools

**Before:**
```bash
video-tool --transcript --input-dir ./clips
```

**After:**
```bash
video-tool transcript --video-path ./clips/output/video.mp4
```

### Running Multiple Steps

**Before:**
```bash
video-tool --all --input-dir ./clips
```

**After:**
```bash
video-tool silence-removal --input-dir ./clips
video-tool concat --input-dir ./clips
video-tool timestamps --input-dir ./clips
video-tool transcript --video-path ./clips/output/video.mp4
# ... etc
```

### Interactive Mode

**Before:**
```bash
video-tool --manual
```

**After:**
Just omit arguments and the tool will prompt you:
```bash
video-tool concat  # Will prompt for input-dir
```

## Tool Requirements

Each tool has clear input requirements:

| Tool | Required Inputs | Optional Inputs |
|------|----------------|-----------------|
| silence-removal | input directory | output directory |
| concat | input directory | output directory, fast mode |
| timestamps | input directory | output directory |
| transcript | video path | - |
| context-cards | video path | - |
| description | transcript path | repo URL |
| seo | transcript path | - |
| linkedin | transcript path | - |
| twitter | transcript path | - |
| bunny-video | video path, library ID, access key | collection ID, caption language |

## Example Workflows

### Complete Pipeline

```bash
#!/bin/bash
set -e

INPUT_DIR="./clips"
VIDEO_PATH="$INPUT_DIR/output/final-video.mp4"
TRANSCRIPT_PATH="$INPUT_DIR/output/transcript.vtt"

video-tool silence-removal --input-dir "$INPUT_DIR"
video-tool concat --input-dir "$INPUT_DIR" --fast-concat
video-tool timestamps --input-dir "$INPUT_DIR"
video-tool transcript --video-path "$VIDEO_PATH"
video-tool description --transcript-path "$TRANSCRIPT_PATH" --repo-url "https://github.com/user/repo"
video-tool seo --transcript-path "$TRANSCRIPT_PATH"
video-tool linkedin --transcript-path "$TRANSCRIPT_PATH"
video-tool twitter --transcript-path "$TRANSCRIPT_PATH"
video-tool bunny-video --video-path "$VIDEO_PATH"
```

### Quick Tasks

```bash
# Just generate a transcript
video-tool transcript --video-path ./my-video.mp4

# Just generate social media posts
video-tool linkedin --transcript-path ./transcript.vtt
video-tool twitter --transcript-path ./transcript.vtt
```

## Technical Details

### Architecture

The new CLI uses Python's `argparse` with subcommands:

```python
# Create main parser
parser = argparse.ArgumentParser(...)
subparsers = parser.add_subparsers(dest="command")

# Add command
concat_parser = subparsers.add_parser("concat")
concat_parser.add_argument("--input-dir")
concat_parser.add_argument("--fast-concat", action="store_true")

# Route to handler
command_handlers = {
    "concat": cmd_concat,
    # ...
}
handler = command_handlers[args.command]
handler(args)
```

### Interactive Prompting

The CLI uses Rich for interactive prompts:

```python
def ask_required_path(prompt_text: str) -> str:
    while True:
        response = Prompt.ask(f"[bold cyan]{prompt_text}[/]", console=console)
        if response:
            return normalize_path(response)
        console.print("[yellow]Please provide a value.[/]")
```

### Backwards Compatibility

The original `main.py` functionality is preserved in `main_old.py`. The new `main.py` simply imports and calls the new CLI, maintaining backwards compatibility for existing scripts.

## Testing

To test the new CLI:

```bash
# Show help
python main.py --help
python main.py concat --help

# Test a command
python main.py concat --input-dir ./test_clips --fast-concat
```

## Future Enhancements

Potential additions for the future:

1. **Sequence command**: Run multiple tools automatically
2. **Config files**: Support for YAML/JSON configuration
3. **Parallel processing**: Run independent tools in parallel
4. **Progress bars**: Better visual feedback for long operations
5. **Dry-run mode**: Preview what will happen without executing
6. **Watch mode**: Automatically process new files in a directory

## Notes

- The old CLI with profiles and `--manual` mode is still available in `main_old.py`
- All existing VideoProcessor methods remain unchanged
- Environment variables (API keys, etc.) work the same way
- Output structure remains consistent
