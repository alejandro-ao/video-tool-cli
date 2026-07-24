"""Tests for social posting commands."""

from unittest.mock import patch

import pytest
from typer.testing import CliRunner

from video_tool.cli import app

runner = CliRunner()


@pytest.mark.unit
def test_twitter_requires_text():
    result = runner.invoke(app, ["upload", "twitter"])
    assert result.exit_code == 1
    assert "--text" in result.stdout or "text" in result.stdout.lower()


@pytest.mark.unit
def test_linkedin_requires_text():
    result = runner.invoke(app, ["upload", "linkedin"])
    assert result.exit_code == 1
    assert "--text" in result.stdout or "text" in result.stdout.lower()


@pytest.mark.unit
def test_twitter_requires_oauth_credentials():
    with patch("video_tool.cli.social_commands.get_credential", return_value=None):
        result = runner.invoke(app, ["upload", "twitter", "--text", "hello"])
        assert result.exit_code == 1
        assert "oauth" in result.stdout.lower() or "x_api_key" in result.stdout.lower()


@pytest.mark.unit
def test_linkedin_requires_token_and_author():
    with patch("video_tool.cli.social_commands.get_credential", return_value=None):
        result = runner.invoke(app, ["upload", "linkedin", "--text", "hello"])
        assert result.exit_code == 1
        assert "token" in result.stdout.lower() or "linkedin" in result.stdout.lower()
