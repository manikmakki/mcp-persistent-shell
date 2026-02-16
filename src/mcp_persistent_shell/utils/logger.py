"""Structured logging setup for MCP persistent shell server."""

import logging
import sys
from typing import Any

from mcp_persistent_shell.config import LoggingConfig


def setup_logging(config: LoggingConfig) -> logging.Logger:
    """Setup structured logging based on configuration."""
    # Map string level to logging constant
    level_map = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }

    log_level = level_map.get(config.level.lower(), logging.INFO)

    # Configure root logger
    logging.basicConfig(
        level=log_level,
        format=(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
            '"logger": "%(name)s", "message": "%(message)s"}'
            if config.format == "json"
            else "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        ),
        handlers=[logging.StreamHandler(sys.stdout)],
    )

    logger = logging.getLogger("mcp_persistent_shell")
    logger.setLevel(log_level)

    return logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance for a specific module."""
    return logging.getLogger(f"mcp_persistent_shell.{name}")
