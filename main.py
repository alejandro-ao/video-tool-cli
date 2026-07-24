"""Backward-compatible entry point that simply delegates to the real CLI.

All CLI logic lives in the video_tool/cli package.
"""

from video_tool.cli import main

if __name__ == "__main__":
    main()
