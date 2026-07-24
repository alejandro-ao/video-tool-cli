# Repository Guidelines

## Project Structure & Module Organization
`main.py` is a thin shim that delegates to the real CLI in the `video_tool/cli/` package (Typer apps: `video`, `generate`, `upload`, `config`). Processing logic lives in the `video_tool/video_processor/` package: each capability is a mixin module (`concatenation.py`, `transcript.py`, `content.py`, `editing.py`, `silence.py`, `download.py`, `deployment.py`, `youtube.py`, `social.py`, `file_management.py`) composed by the `VideoProcessor` facade in `processor.py`. Shared config/credentials live in `video_tool/config.py` (state under `~/.config/video-tool/`, including logs). Automation helpers sit in `scripts/` for ad-hoc workflows. Tests, fixtures, and sample assets reside in `tests/`, with reusable data under `tests/test_data/`. Patch third-party clients in tests at the module that imports them (e.g. `video_tool.video_processor.transcript.VideoFileClip`).

## Build, Test, and Development Commands
Install dependencies (including dev extras) with:
```bash
uv sync --group dev
```
Run the CLI locally (keys via `video-tool config keys`, exported env vars, or a project-local `.env`):
```bash
uv run video-tool --help
python main.py  # equivalent shim
```
Exercise the suite before opening a PR:
```bash
uv run pytest
uv run pytest -m "unit and not slow"
uv run pytest --cov=video_tool --cov=main --cov-report=term-missing
```

## Coding Style & Naming Conventions
Follow idiomatic Python 3.11 with 4-space indents, type hints on public interfaces, and docstrings that describe side effects. Use `snake_case` for functions and module-level variables, `PascalCase` for classes, and uppercase `CONSTANTS`. Prefer pathlib for filesystem paths (see `video_tool/video_processor/`) and route logging through `loguru`. Keep YAML prompt keys in `prompts.yaml` kebab-cased and stable, and store temporary files under the caller’s `output/` directory. CLI commands resolve output paths via `video_tool/cli/paths.py::resolve_output_path` instead of hand-rolling resolution blocks.

## Testing Guidelines
Pytest is configured via `pytest.ini`; tests live beside their fixtures under `tests/`. Name new files `test_<feature>.py`, and mark scope with `@pytest.mark.unit`, `@pytest.mark.integration`, or related markers. Use factories in `tests/test_data/mock_generators.py` for sample video or transcript payloads rather than hand-rolled fixtures. When new behavior touches external services, gate those tests behind `requires_api` and supply contract doubles so the default suite stays fast.

## Commit & Pull Request Guidelines
The history follows Conventional Commits (`feat(video_processor): …`, `test: …`). Match that format, keep subjects under ~72 characters, and describe breaking changes in the body. PRs should summarize the workflow impact, list manual or automated checks (`pytest`, coverage, lint), and link the tracking issue. Include screenshots or sample outputs when modifying generated copy so reviewers can verify Markdown rendering or media artifacts.

### Atomic Commits
When committing changes, **never bundle all modifications into a single commit**. Instead, split the work into multiple granular commits, each addressing exactly one logical change. For example, if you fixed a bug, updated a docstring, and added a test, those should be three separate commits in this order:

1. `fix(module): resolve off-by-one error in segment splitting`
2. `docs(module): update docstring for split_segments`
3. `test(module): add coverage for edge case in segment splitting`

Each commit must:
- Contain only the files relevant to that specific change.
- Have a detailed subject line following Conventional Commits.
- Include a body when the reasoning is not obvious from the subject alone.
- Leave the repository in a passing state (`pytest` should succeed after every commit).

This makes the history easy to bisect, revert, and review.

## Security & Configuration Tips
Never hard-code API keys; prefer `video-tool config keys` (stored in `~/.config/video-tool/credentials.yaml` with 0600 perms), exported env vars, or a local `.env` (loaded via `python-dotenv`, never overriding exported vars). Ensure `ffmpeg` is discoverable on `$PATH` before testing video operations, and purge any residual media from commits—use `.gitignore` patterns under `build/` and `processed/`.
