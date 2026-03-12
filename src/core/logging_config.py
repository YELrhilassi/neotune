"""Centralized logging configuration for NeoTune."""

import logging
import sys
from pathlib import Path
from typing import Optional


def setup_logging(
    level: int = logging.INFO,
    log_file: Optional[Path] = None,
    enable_console: bool = True,
) -> logging.Logger:
    """Configure application-wide logging.

    Args:
        level: Logging level (default: INFO)
        log_file: Optional path to log file
        enable_console: Whether to log to console (default: True)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("neotune")
    logger.setLevel(level)
    logger.handlers = []  # Clear existing handlers

    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """Get logger instance for module.

    Args:
        name: Module name (default: "neotune")

    Returns:
        Logger instance
    """
    if name:
        return logging.getLogger(f"neotune.{name}")
    return logging.getLogger("neotune")


class LogMixin:
    """Mixin class to add logging capability to any class."""

    @property
    def logger(self) -> logging.Logger:
        """Get logger for class."""
        return logging.getLogger(f"neotune.{self.__class__.__name__}")
