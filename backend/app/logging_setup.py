"""Central logging configuration."""

from __future__ import annotations

import logging
import sys


def configure_logging(level_name: str) -> None:
    """Configure root logger once at application startup."""
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )
