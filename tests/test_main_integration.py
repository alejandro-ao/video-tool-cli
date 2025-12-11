"""Integration shim tests for the thin main.py wrapper."""

import importlib
from unittest.mock import patch


def test_main_delegates_to_cli():
    """main.main should delegate execution to video_tool.cli.main."""
    with patch("video_tool.cli.main") as mock_cli_main:
        import main

        importlib.reload(main)
        main.main()
        mock_cli_main.assert_called_once()
