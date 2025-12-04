import argparse

import pytest

from video_tool import cli


@pytest.mark.unit
def test_cmd_pipeline_uses_packaged_runner(monkeypatch):
    """Ensure the pipeline command dispatches to the packaged runner module."""
    called: dict[str, list[str]] = {}

    def fake_main(argv: list[str] | None = None) -> None:
        called["argv"] = argv or []

    monkeypatch.setattr("video_tool.run_full_pipeline.main", fake_main)

    args = argparse.Namespace(cli_bin="custom-cli")

    cli.cmd_pipeline(args)

    assert called["argv"] == ["--cli-bin", "custom-cli"]
