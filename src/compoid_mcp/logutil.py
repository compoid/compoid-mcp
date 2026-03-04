"""Logging configuration for Compoid MCP Server."""

import logging
import sys
from typing import Optional

from compoid_mcp.config import config


def setup_logging(logger_name: Optional[str] = None) -> logging.Logger:
    """Set up logging configuration."""
    logger = logging.getLogger(logger_name or "compoid_mcp")

    # Clear any existing handlers
    logger.handlers.clear()

    # Set log level
    level = getattr(logging, config.log_level.upper(), logging.INFO)
    logger.setLevel(level)

    # Console handler - use stderr to avoid corrupting MCP JSON-RPC on stdout
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(level)
    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    logger.propagate = False

    # Suppress httpx logging to prevent stdout pollution in MCP
    httpx_logger = logging.getLogger("httpx")
    httpx_logger.setLevel(logging.WARNING)
    httpx_logger.propagate = False

    return logger

logger = setup_logging()
