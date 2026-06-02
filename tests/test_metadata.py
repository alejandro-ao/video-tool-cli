"""Unit tests for video_tool.metadata module (new in refactor/project-audit-fixes PR).

These tests verify the shared metadata.json read/write helpers. On the current
branch (pre-merge) the module may not exist yet; the tests are designed to run
both before and after the PR merge.
"""

import importlib
import json
from pathlib import Path

import pytest

try:
    from video_tool.metadata import read_metadata, write_metadata
    METADATA_MODULE_AVAILABLE = True
except ImportError:
    METADATA_MODULE_AVAILABLE = False


@pytest.mark.skipif(
    not METADATA_MODULE_AVAILABLE,
    reason="video_tool.metadata not yet available (merge refactor/project-audit-fixes PR first)",
)
class TestReadMetadata:
    """Test read_metadata helper."""

    def test_read_metadata_from_valid_file(self, tmp_path: Path) -> None:
        metadata_path = tmp_path / "metadata.json"
        data = {"video_id": "abc123", "title": "My Video"}
        metadata_path.write_text(json.dumps(data), encoding="utf-8")

        result = read_metadata(metadata_path)
        assert result == data

    def test_read_metadata_returns_none_when_file_missing(self, tmp_path: Path) -> None:
        missing = tmp_path / "nonexistent.json"
        result = read_metadata(missing)
        assert result is None

    def test_read_metadata_returns_none_on_invalid_json(self, tmp_path: Path) -> None:
        bad_json = tmp_path / "metadata.json"
        bad_json.write_text("{invalid json content", encoding="utf-8")

        result = read_metadata(bad_json)
        assert result is None

    def test_read_metadata_returns_none_on_empty_file(self, tmp_path: Path) -> None:
        empty = tmp_path / "metadata.json"
        empty.write_text("", encoding="utf-8")

        result = read_metadata(empty)
        assert result is None

    def test_read_metadata_handles_nested_data(self, tmp_path: Path) -> None:
        metadata_path = tmp_path / "metadata.json"
        data = {
            "social": {
                "x": {"post_url": "https://x.com/123"},
                "linkedin": {"post_url": "https://linkedin.com/456"},
            },
            "timestamps": [
                {"start": "00:00:00.000", "end": "00:02:30.000", "title": "Intro"},
            ],
        }
        metadata_path.write_text(json.dumps(data), encoding="utf-8")

        result = read_metadata(metadata_path)
        assert result["social"]["x"]["post_url"] == "https://x.com/123"
        assert len(result["timestamps"]) == 1

    def test_read_metadata_with_unicode(self, tmp_path: Path) -> None:
        metadata_path = tmp_path / "metadata.json"
        data = {"title": "Vídeo en español — Ö UTF-8 ñ"}
        metadata_path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")

        result = read_metadata(metadata_path)
        assert result["title"] == "Vídeo en español — Ö UTF-8 ñ"


@pytest.mark.skipif(
    not METADATA_MODULE_AVAILABLE,
    reason="video_tool.metadata not yet available (merge refactor/project-audit-fixes PR first)",
)
class TestWriteMetadata:
    """Test write_metadata helper."""

    def test_write_metadata_creates_file(self, tmp_path: Path) -> None:
        metadata_path = tmp_path / "metadata.json"
        data = {"video_id": "xyz789"}

        write_metadata(metadata_path, data)

        assert metadata_path.exists()
        content = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert content == data

    def test_write_metadata_creates_parent_directories(self, tmp_path: Path) -> None:
        metadata_path = tmp_path / "subdir" / "nested" / "metadata.json"
        data = {"key": "value"}

        write_metadata(metadata_path, data)

        assert metadata_path.exists()
        assert metadata_path.parent.is_dir()
        content = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert content == data

    def test_write_metadata_pretty_prints_json(self, tmp_path: Path) -> None:
        metadata_path = tmp_path / "metadata.json"
        data = {"a": 1, "b": 2}

        write_metadata(metadata_path, data)

        raw = metadata_path.read_text(encoding="utf-8")
        assert "\n" in raw
        assert '"a"' in raw

    def test_write_metadata_overwrites_existing(self, tmp_path: Path) -> None:
        metadata_path = tmp_path / "metadata.json"
        metadata_path.write_text(json.dumps({"old": True}), encoding="utf-8")

        new_data = {"new": True, "updated": "yes"}
        write_metadata(metadata_path, new_data)

        content = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert "old" not in content
        assert content["new"] is True

    def test_write_metadata_handles_unicode(self, tmp_path: Path) -> None:
        metadata_path = tmp_path / "metadata.json"
        data = {"description": "日本語テスト émojis 🚀"}

        write_metadata(metadata_path, data)

        content = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert content["description"] == "日本語テスト émojis 🚀"

    def test_write_metadata_on_readonly_dir_does_not_raise(self, tmp_path: Path) -> None:
        """write_metadata should not raise; it logs a warning on OSError."""
        import os
        import stat

        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        metadata_path = readonly_dir / "metadata.json"

        os.chmod(str(readonly_dir), stat.S_IRUSR | stat.S_IXUSR)

        try:
            write_metadata(metadata_path, {"key": "value"})
            assert not metadata_path.exists()
        finally:
            os.chmod(str(readonly_dir), stat.S_IRWXU)

    def test_roundtrip_read_write(self, tmp_path: Path) -> None:
        metadata_path = tmp_path / "metadata.json"
        original = {
            "bunny_video": {
                "video_id": "vid-abc",
                "library_id": "lib-1",
            },
            "transcript": "Some transcript content",
            "timestamps": [
                {"start": "00:00:00", "end": "00:01:30", "title": "Opening"},
            ],
        }

        write_metadata(metadata_path, original)
        result = read_metadata(metadata_path)
        assert result == original

    def test_merge_scenario_reads_existing_and_writes_back(self, tmp_path: Path) -> None:
        metadata_path = tmp_path / "metadata.json"
        initial = {"existing_key": "existing_value"}
        write_metadata(metadata_path, initial)

        existing = read_metadata(metadata_path) or {}
        existing["new_key"] = "new_value"
        write_metadata(metadata_path, existing)

        final = read_metadata(metadata_path)
        assert final["existing_key"] == "existing_value"
        assert final["new_key"] == "new_value"