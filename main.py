"""
Backward-compatible entry point that simply delegates to the real CLI.
All CLI logic lives in video_tool/cli.py.
"""

from video_tool.cli import main

if __name__ == "__main__":
    main()
