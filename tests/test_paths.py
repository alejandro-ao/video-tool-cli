"""Unit tests for video_tool.cli.paths module (new in refactor/project-audit-fixes PR).

The PR introduces resolve_output_path to eliminate duplicated path resolution
across all CLI commands. These tests ensure the shared utility behaves correctly.

On the current branch (pre-merge) the module may not exist yet; tests will
be skipped until the PR is merged.
"""

import importlib
from pathlib import Path
from unittest.mock import patch

import pytest

try:
    from video_tool.cli.paths import resolve_output_path
    PATHS_MODULE_AVAILABLE = True
except ImportError:
    PATHS_MODULE_AVAILABLE = False


@pytest.mark.skipif(
    not PATHS_MODULE_AVAILABLE,
    reason="video_tool.cli.paths not yet available (merge refactor/project-audit-fixes PR first)",
)
class TestResolveOutputPath:
    """Test the resolve_output_path utility."""

    def test_explicit_absolute_path(self, tmp_path: Path) -> None:
        output = tmp_path / "output" / "result.mp4"
        input_path = tmp_path / "input"
        input_path.mkdir()

        result = resolve_output_path(output, input_path, "default.mp4")

        assert result == output
        assert result.parent.exists()

    def test_explicit_relative_path_resolves_against_input(self, tmp_path: Path) -> None:
        input_path = tmp_path / "project"
        input_path.mkdir()
        relative_output = Path("subdir/video.mp4")

        result = resolve_output_path(relative_output, input_path, "default.mp4")

        assert result == input_path / "subdir" / "video.mp4"
        assert result.parent.exists()

    def test_none_output_uses_default_name(self, tmp_path: Path) -> None:
        input_path = tmp_path / "project"
        input_path.mkdir()

        result = resolve_output_path(None, input_path, "result.mp4")

        assert result == input_path / "result.mp4"
        assert result.parent.exists()

    def test_suffix_override_when_different(self, tmp_path: Path) -> None:
        input_path = tmp_path / "project"
        input_path.mkdir()
        output = input_path / "video.mp3"

        result = resolve_output_path(output, input_path, "default.mp4", suffix=".mp4")

        assert result.suffix == ".mp4"
        assert result.name == "video.mp4"

    def test_suffix_preserved_when_matching(self, tmp_path: Path) -> None:
        input_path = tmp_path / "project"
        input_path.mkdir()
        output = input_path / "video.mp4"

        result = resolve_output_path(output, input_path, "default.mp4", suffix=".mp4")

        assert result.suffix == ".mp4"
        assert result.name == "video.mp4"

    def test_suffix_not_applied_when_none(self, tmp_path: Path) -> None:
        input_path = tmp_path / "project"
        input_path.mkdir()
        output = input_path / "video.mp3"

        result = resolve_output_path(output, input_path, "default.mp4", suffix=None)

        assert result.suffix == ".mp3"

    def test_creates_parent_directories(self, tmp_path: Path) -> None:
        input_path = tmp_path / "project"
        input_path.mkdir()
        deep_output = input_path / "deep" / "nested" / "output.mp4"

        result = resolve_output_path(deep_output, input_path, "default.mp4")

        assert result.parent.exists()
        assert result.parent.is_dir()

    def test_prompt_mode_when_output_none_and_prompt_true(self, tmp_path: Path) -> None:
        input_path = tmp_path / "project"
        input_path.mkdir()

        with patch("video_tool.cli.paths.ask_path", return_value="/custom/path/video.mp4"):
            result = resolve_output_path(
                None, input_path, "default.mp4", prompt=True
            )

        assert "video.mp4" in str(result)

    def test_prompt_mode_uses_default_when_user_empty(self, tmp_path: Path) -> None:
        input_path = tmp_path / "project"
        input_path.mkdir()

        with patch("video_tool.cli.paths.ask_path", return_value=None):
            result = resolve_output_path(
                None, input_path, "default.mp4", prompt=True
            )

        assert result == input_path / "default.mp4"

    def test_prompt_mode_with_custom_text(self, tmp_path: Path) -> None:
        input_path = tmp_path / "project"
        input_path.mkdir()

        with patch("video_tool.cli.paths.ask_path", return_value="/output/video.mp4") as mock_ask:
            resolve_output_path(
                None, input_path, "default.mp4",
                prompt=True, prompt_text="Where should I save this?",
            )
            mock_ask.assert_called_once_with(
                "Where should I save this?", required=False
            )

    def test_prompt_mode_relative_path_resolved(self, tmp_path: Path) -> None:
        input_path = tmp_path / "project"
        input_path.mkdir()

        with patch("video_tool.cli.paths.ask_path", return_value="relative/video.mp4"):
            result = resolve_output_path(
                None, input_path, "default.mp4", prompt=True
            )

        assert result == input_path / "relative" / "video.mp4"

    def test_absolute_path_from_prompt_not_relativized(self, tmp_path: Path) -> None:
        input_path = tmp_path / "project"
        input_path.mkdir()
        absolute = tmp_path / "absolute" / "video.mp4"

        with patch("video_tool.cli.paths.ask_path", return_value=str(absolute)):
            result = resolve_output_path(
                None, input_path, "default.mp4", prompt=True
            )

        assert result == absolute

    def test_default_name_suffix_interaction(self, tmp_path: Path) -> None:
        input_path = tmp_path / "project"
        input_path.mkdir()

        result = resolve_output_path(
            None, input_path, "result.txt", suffix=".mp4"
        )

        assert result.name == "result.mp4"
        assert result.suffix == ".mp4"

    def test_explicit_path_is_normalized(self, tmp_path: Path) -> None:
        input_path = tmp_path / "project"
        input_path.mkdir()

        with patch("video_tool.cli.paths.normalize_path", side_effect=lambda x: x):
            result = resolve_output_path(
                tmp_path / "output" / "video.mp4", input_path, "default.mp4"
            )

        assert result == tmp_path / "output" / "video.mp4"