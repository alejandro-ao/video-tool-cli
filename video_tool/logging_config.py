"""Logging configuration for video-tool CLI.

Suppresses loguru terminal output by default, routing all logs to a file
under the user config directory (never the caller's working directory).
Optional verbose mode adds filtered stderr output.
"""

from __future__ import annotations

import sys

from loguru import logger

from video_tool.config import CONFIG_DIR

LOG_DIR = CONFIG_DIR / "logs"
LOG_PATH = LOG_DIR / "video_processor.log"

_configured = False


def configure_logging(verbose: bool = False) -> None:
    """Configure loguru to suppress terminal noise.

    Args:
        verbose: If True, also log INFO+ to stderr with minimal formatting.
    """
    global _configured

    if _configured:
        return

    # Remove default stderr handler
    logger.remove()

    # File handler for all logs
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(LOG_PATH),
        rotation="1 day",
        retention="1 week",
        level="DEBUG",
    )

    # Optional stderr handler for verbose mode
    if verbose:
        logger.add(
            sys.stderr,
            level="INFO",
            format="<dim>{time:HH:mm:ss}</dim> | {message}",
        )

    _configured = True


def reset_logging() -> None:
    """Reset logging configuration (for testing)."""
    global _configured
    logger.remove()
    _configured = False
