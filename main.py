"""
Main entry point for video-tool CLI.

This file maintains backwards compatibility by importing and running the new CLI.
For new code, use: video_tool.cli directly or the 'video-tool' command.
"""

from video_tool.cli import main

if __name__ == "__main__":
    main()
