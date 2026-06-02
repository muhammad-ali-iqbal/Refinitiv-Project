"""
logger.py — Consistent logging across all pipeline modules.
Writes to both stdout and a rolling log file in the output root.
"""

import logging
import os
from config.settings import OUTPUT_ROOT

LOG_FILE = os.path.join(OUTPUT_ROOT, "_pipeline.log")


def get_logger(name: str) -> logging.Logger:
    os.makedirs(OUTPUT_ROOT, exist_ok=True)

    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # Already configured

    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File handler
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger
