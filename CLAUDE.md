# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install (dev)
uv tool install --editable .

# Run CLI
video-tool --help
video-tool pipeline  # non-interactive full workflow

# Tests
pytest                              # all tests
pytest -m "unit and not slow"       # fast unit tests
pytest --cov=video_tool --cov=main  # with coverage
```

## Architecture

**Entry points**: `main.py` → `video_tool/cli.py` (interactive CLI with 17+ commands)

**VideoProcessor (mixin pattern)** in `video_tool/video_processor/`:
- `base.py`: Core config, LLM clients (OpenAI/Groq via native SDKs), loguru logging
- `concatenation.py`: ffmpeg video joining, fast concat, timestamp generation
- `content.py`: Description, SEO, social posts, context cards (uses prompts.yaml)
- `transcript.py`: Groq Whisper transcription
- `deployment.py`: Bunny.net CDN uploads
- `processor.py`: Facade composing all mixins

**CLI commands** (all support interactive prompts when args omitted):
- Video: `silence-removal`, `concat`, `timestamps`, `transcript`, `thumbnail`
- Content: `description`, `seo`, `linkedin`, `twitter`, `context-cards`
- Deploy: `bunny-upload`, `bunny-transcript`, `bunny-chapters`
- Automation: `pipeline` (orchestrates full workflow)

**Outputs** go to `output/` subdirectory: `*.mp4`, `transcript.vtt`, `timestamps.json`, `description.md`, `keywords.txt`, social posts, `metadata.json`

## Environment

Required in `.env`:
- `GROQ_API_KEY` - transcription (Groq Whisper Large V3 Turbo)
- `OPENAI_API_KEY` - content generation (descriptions, SEO, social posts, timestamps)

Optional (Bunny.net): `BUNNY_LIBRARY_ID`, `BUNNY_ACCESS_KEY`, `BUNNY_COLLECTION_ID`

## Testing

Test markers in `pytest.ini`: `unit`, `integration`, `slow`, `requires_ffmpeg`, `requires_api`

Fixtures in `tests/conftest.py`. Mock data factories in `tests/test_data/mock_generators.py`.

## Conventions

- Python 3.11+, type hints, pathlib for paths
- Conventional Commits: `feat(video_processor): ...`, `test: ...`
- YAML prompt keys in `prompts.yaml` are kebab-cased
