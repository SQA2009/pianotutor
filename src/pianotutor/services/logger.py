"""Application-wide logging setup.

Kept deliberately simple: one rotating file handler under the user's app-data
directory plus a console handler, both attached to the ``pianotutor`` root
logger. Modules should just use ``logging.getLogger(__name__)``.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

_CONFIGURED = False


def configure_logging(log_dir: Path, level: int = logging.INFO) -> None:
    """Idempotently configure logging. Safe to call multiple times."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "pianotutor.log"

    root = logging.getLogger("pianotutor")
    root.setLevel(level)

    fmt = logging.Formatter(
        fmt="%(asctime)s %(levelname)-7s %(threadName)-16s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=2_000_000, backupCount=3, encoding="utf-8"
    )
    file_handler.setFormatter(fmt)
    root.addHandler(file_handler)

    console_handler = logging.StreamHandler(stream=sys.stdout)
    console_handler.setFormatter(fmt)
    root.addHandler(console_handler)

    _CONFIGURED = True
    root.info("Logging configured. Writing to %s", log_file)
