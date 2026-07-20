"""
Centralized logging configuration for VaultDocs.
"""

import logging
import sys


def configure_logging() -> None:
    """
    Configure the application's logging system.
    """

    logging.basicConfig(
        level=logging.INFO,
        format=("%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"),
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    """
    Return a configured logger instance.
    """

    return logging.getLogger(name)
