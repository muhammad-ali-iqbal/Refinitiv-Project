"""
utils/logger.py — Configures logging to both console and file.
"""

import logging
import os


def setup_logger(output_root: str) -> None:
    os.makedirs(output_root, exist_ok=True)
    log_path = os.path.join(output_root, "_pipeline.log")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        handlers=[
            logging.FileHandler(log_path, encoding="utf-8"),
            logging.StreamHandler(),
        ],
    )
