"""Compatibility wrapper that defers to the packaged pipeline runner."""

from pathlib import Path
import sys

# Allow running directly from a source checkout without installing the package.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from video_tool.run_full_pipeline import main


if __name__ == "__main__":
    main()
