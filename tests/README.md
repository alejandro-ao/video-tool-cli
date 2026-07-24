# Video Tool Test Suite

Unit and CLI-level tests for the video-tool package.

## Running Tests

```bash
# Install dependencies (including dev extras)
uv sync --group dev

# Run all tests
uv run pytest

# Fast unit tests only
uv run pytest -m "unit and not slow"

# With coverage
uv run pytest --cov=video_tool --cov=main --cov-report=term-missing
```

Pytest is configured in `pytest.ini` at the repo root (`[pytest]` section).

## Markers

- **unit**: Unit tests for individual methods or CLI commands
- **integration**: Integration tests for complete workflows
- **slow**: Tests that take longer to execute
- **requires_ffmpeg**: Tests requiring FFmpeg installation
- **requires_api**: Tests requiring API keys (OpenAI, Groq)
- **requires_gpu**: Tests requiring GPU acceleration

## Structure

```
tests/
├── conftest.py                    # Shared fixtures (temp_dir, mock_video_processor, ...)
├── test_data/                     # Mock generators and sample API payloads
│   ├── mock_generators.py         # Mock file generators
│   └── sample_data.py             # Sample responses (Groq, OpenAI, ffprobe)
├── test_cli_video.py              # CLI tests: concat, timestamps, extract-audio, cut, silence-removal
├── test_cli_youtube.py            # CLI tests: youtube-video/-transcript/-metadata
├── test_cli_generate.py           # CLI tests: transcript, description, context-cards
├── test_cli_deploy.py             # CLI tests: Bunny caption language fallback
├── test_cli_social.py             # CLI tests: X/LinkedIn uploads
├── test_cli_video_download.py     # CLI tests: download output paths
├── test_concatenation_encoders.py # Concatenation and encoder/GPU detection
├── test_content_generation.py     # Mixin tests: timestamps, transcript, description, social copy
├── test_editing.py                # Mixin tests: trim, cut, speed, extract-segment
├── test_bunny_deployment.py       # Bunny.net deployment mixin
├── test_deployment_credentials.py # Bunny credential resolution
├── test_config.py                 # Config/credential storage
├── test_file_methods.py           # File discovery and metadata extraction
├── test_metadata.py               # metadata.json helpers
├── test_paths.py                  # resolve_output_path helper
├── test_prompt_keys.py            # prompts.yaml key integrity
└── test_main_integration.py       # main.py shim and .env loading
```

## Mocking Guidelines

Each `video_tool/video_processor` submodule imports its third-party
dependencies directly. Patch them at the module that uses them:

```python
patch("video_tool.video_processor.transcript.VideoFileClip")
patch("video_tool.video_processor.base.Groq")
patch("video_tool.video_processor.content.logger")
```

For CLI commands, patch the names imported into the command module:

```python
patch("video_tool.cli.video_commands.VideoProcessor")
patch("video_tool.cli.deploy_commands._check_youtube_credentials")
```

Use factories in `tests/test_data/mock_generators.py` for sample video or
transcript payloads rather than hand-rolled fixtures. Gate tests that touch
external services behind `requires_api` and supply contract doubles so the
default suite stays fast.

## Writing New Tests

- Name files `test_<feature>.py`; follow the AAA pattern (Arrange, Act, Assert)
- Mark scope with `@pytest.mark.unit` / `@pytest.mark.integration`
- Mock external dependencies (APIs, subprocess, filesystem outside tmp_path)
- Keep tests independent and assert non-zero exit codes for CLI failures
