# Video Processing Tool

Automate Alejandro's YouTube production workflow end to end. Given a directory of source MP4 clips, the script can clean the footage, join the clips, create chapter timestamps, transcribe the final video, and generate all supporting copy for publishing.

## Features
- Silence trimming with `pydub` to tighten raw footage before assembly.
- MP4 concatenation with `ffmpeg`, including optional fast-path when reprocessing is unnecessary.
- Automatic chapter map (`timestamps.json`) with ISO-formatted timecode.
- Whisper transcription (`transcript.vtt`) via `OPENAI_API_KEY`.
- Markdown description, SEO keywords, and social posts derived from `prompts.yaml`.
- Optional duration CSV export for analytics.

## Requirements
- Python 3.11+
- Installed dependencies: `pip install -r requirements.txt`
- `ffmpeg` available on the system path
- Environment variables:
  - `OPENAI_API_KEY` (required for Whisper and text generation)
  - `GROQ_API_KEY` (required for additional LLM calls)

## Usage
1. Install dependencies and export the required API keys.
2. Run the CLI:
   ```bash
   python main.py
   ```
3. Provide the target directory when prompted. The tool will list each available operation and let you skip steps such as silence removal, concatenation, transcript generation, description creation, SEO keywords, and social posts.
4. Outputs are written back to the input directory:
   - Processed clips: `processed/`
   - Final video: `<input_dir>/<date>_<title>.mp4`
   - Chapters: `timestamps.json`
   - Transcript: `transcript.vtt`
   - Description: `description.md`
   - SEO keywords: `keywords.txt`
   - Social copy: `linkedin.md`, `twitter.txt`

All actions are logged to `video_processor.log` so you can review progress and debug any failures.

## Additional Tools
- `VideoProcessor.extract_duration_csv()` exports `video_metadata.csv` summarizing clip lengths and creation dates across a directory tree.

For outstanding improvements and roadmap items, see `todo.md`.
