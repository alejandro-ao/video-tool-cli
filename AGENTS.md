# Repository Guidelines

## Project Structure & Module Organization
`main.py` is the interactive CLI that coordinates every processing stage. Core logic lives in `video_tool/video_processor.py`, which bundles operations such as silence removal, concatenation, transcription, and content generation while persisting logs to `video_processor.log`. The MCP tooling and server adapters are organized under `mcp_server/`, and automation helpers sit in `scripts/` for ad-hoc workflows. Tests, fixtures, and sample assets reside in `tests/`, with reusable data under `tests/test_data/`.

## Build, Test, and Development Commands
Install runtime dependencies with:
```bash
python -m pip install -r requirements.txt
```
Optional dev extras:
```bash
uv pip install -r pyproject.toml#dev
```
Run the CLI locally after exporting `OPENAI_API_KEY` and `GROQ_API_KEY`:
```bash
python main.py
```
Exercise the suite before opening a PR:
```bash
pytest
pytest -m "unit and not slow"
pytest --cov=video_tool --cov=main --cov-report=term-missing
```

## Coding Style & Naming Conventions
Follow idiomatic Python 3.11 with 4-space indents, type hints on public interfaces, and docstrings that describe side effects. Use `snake_case` for functions and module-level variables, `PascalCase` for classes, and uppercase `CONSTANTS`. Prefer pathlib for filesystem paths (see `video_tool/video_processor.py`) and route logging through `loguru`. Keep YAML prompt keys in `prompts.yaml` kebab-cased and stable, and store temporary files under the caller’s `output/` directory.

## Testing Guidelines
Pytest is configured via `pytest.ini`; tests live beside their fixtures under `tests/`. Name new files `test_<feature>.py`, and mark scope with `@pytest.mark.unit`, `@pytest.mark.integration`, or related markers. Use factories in `tests/test_data/mock_generators.py` for sample video or transcript payloads rather than hand-rolled fixtures. When new behavior touches external services, gate those tests behind `requires_api` and supply contract doubles so the default suite stays fast.

## Commit & Pull Request Guidelines
The history follows Conventional Commits (`feat(video_processor): …`, `test: …`). Match that format, keep subjects under ~72 characters, and describe breaking changes in the body. PRs should summarize the workflow impact, list manual or automated checks (`pytest`, coverage, lint), and link the tracking issue. Include screenshots or sample outputs when modifying generated copy so reviewers can verify Markdown rendering or media artifacts.

## Security & Configuration Tips
Never hard-code API keys; rely on a local `.env` loaded via `python-dotenv`. Ensure `ffmpeg` is discoverable on `$PATH` before testing video operations, and purge any residual media from commits—use `.gitignore` patterns under `build/` and `processed/`.
