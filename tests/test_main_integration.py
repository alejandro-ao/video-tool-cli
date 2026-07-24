"""Integration shim tests for the thin main.py wrapper."""

import importlib
import os
from pathlib import Path
from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from video_tool.cli import app

runner = CliRunner()


def test_main_delegates_to_cli():
    """main.main should delegate execution to video_tool.cli.main."""
    with patch("video_tool.cli.main") as mock_cli_main:
        import main

        importlib.reload(main)
        main.main()
        mock_cli_main.assert_called_once()


@pytest.mark.unit
def test_cli_loads_dotenv_from_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """A .env file in the working directory is picked up by every command."""
    var = "VIDEO_TOOL_DOTENV_TEST_VAR"
    monkeypatch.delenv(var, raising=False)
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(f"{var}=from-dotenv\n")

    # Any command triggers the app callback that loads .env; this one exits
    # early (invalid input) but the callback has already run.
    result = runner.invoke(app, ["video", "info", "-i", "missing.mp4"])

    assert result.exit_code == 1
    assert os.environ.get(var) == "from-dotenv"


@pytest.mark.unit
def test_cli_dotenv_does_not_override_exported_vars(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exported environment variables win over .env file values."""
    var = "VIDEO_TOOL_DOTENV_TEST_VAR"
    monkeypatch.setenv(var, "exported")
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(f"{var}=from-dotenv\n")

    runner.invoke(app, ["video", "info", "-i", "missing.mp4"])

    assert os.environ.get(var) == "exported"
