"""
bloom.core.logger
-----------------
Centralised logging setup for Bloom Terminal.
Usage:
    from bloom.core.logger import get_logger
    log = get_logger(__name__)
    log.info("started")
"""

import logging
import os
from bloom.core.paths import DATA_DIR

_LOG_FILE = os.path.join(DATA_DIR, "logs", "bloom.log")

def _setup_root_logger() -> logging.Logger:
    logger = logging.getLogger("bloom")
    if logger.handlers:
        return logger  # already configured

    logger.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler (only WARNING+ by default to keep terminal clean)
    ch = logging.StreamHandler()
    ch.setLevel(logging.WARNING)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File handler (DEBUG+)
    try:
        os.makedirs(os.path.dirname(_LOG_FILE), exist_ok=True)
        fh = logging.FileHandler(_LOG_FILE, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError:
        pass  # If log dir isn't writable, just skip file logging

    return logger


_root = _setup_root_logger()


def get_logger(name: str) -> logging.Logger:
    """Return a child logger namespaced under 'bloom'."""
    if not name.startswith("bloom"):
        name = f"bloom.{name}"
    return logging.getLogger(name)
