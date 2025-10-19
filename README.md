# Video Processing Tool

Automate Alejandro's YouTube production workflow end to end. Given a directory of source MP4 clips, the script can clean the footage, join the clips, create chapter timestamps, transcribe the final video, and generate all supporting copy for publishing.

## Features
- Silence trimming with `pydub` to tighten raw footage before assembly.
- MP4 concatenation with `ffmpeg`, including optional fast-path when reprocessing is unnecessary.
- Automatic chapter map (`timestamps.json`) with ISO-formatted timecode.
- Whisper transcription (`transcript.vtt`) via `OPENAI_API_KEY`.
- Thumbnail artwork generation via OpenAI's responses API (gpt-5 + image generation tool) using your prompt, automatically mapped to OpenAI's supported image sizes.
- Markdown description, SEO keywords, and social posts derived from `prompts.yaml`.
- Optional Bunny.net deployment with independent toggles for uploading the final cut, chapters, and transcript captions.
- Optional duration CSV export for analytics.

## Requirements
- Python 3.11+
- Installed dependencies: `pip install -r requirements.txt`
- `ffmpeg` available on the system path
- Environment variables:
  - `OPENAI_API_KEY` (required for Whisper and text generation)
  - `GROQ_API_KEY` (required for additional LLM calls)
  - *(Optional)* Bunny Stream deployment:
    - `BUNNY_LIBRARY_ID`
    - `BUNNY_ACCESS_KEY`
    - `BUNNY_COLLECTION_ID`
    - `BUNNY_CAPTION_LANGUAGE` (defaults to `en`)
    - `BUNNY_VIDEO_ID` (for metadata-only updates)

## Usage
1. Install dependencies and export the required API keys.
2. Run the CLI:
   ```bash
   python main.py
   ```
3. Provide the target directory when prompted. The tool will list each available operation and let you skip steps such as silence removal, concatenation, transcript generation, description creation, SEO keywords, and social posts.
   > Tip: When you upload chapters or captions without re-uploading the video, wait for Bunny Stream to finish processing the asset and supply the existing video ID (prompt or `BUNNY_VIDEO_ID`).
4. Outputs are written to an `output/` subdirectory inside your input directory:
   - Processed clips: `processed/` (remains alongside the raw footage)
   - Final video: `output/<date>_<title>.mp4`
   - Chapters: `output/timestamps.json`
   - Transcript: `output/transcript.vtt`
   - Description: `output/description.md`
   - SEO keywords: `output/keywords.txt`
   - Social copy: `output/linkedin_post.md`, `output/twitter_post.md`

All actions are logged to `video_processor.log` so you can review progress and debug any failures.

For a full reference of CLI commands and flags, see `docs/cli_manual.md`.

## Additional Tools
- `VideoProcessor.extract_duration_csv()` exports `video_metadata.csv` summarizing clip lengths and creation dates across a directory tree.

## Testing
Run the automated suite to exercise the CLI and processing workflows:

```bash
pytest
```

If you prefer using `uv`, execute `uv run pytest` instead.

For outstanding improvements and roadmap items, see `todo.md`.
