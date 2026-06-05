"""
utils/checkpoint.py — Simple JSON-backed crash recovery.
"""

import json
import os
import logging
from config.settings import CHECKPOINT_FILE

log = logging.getLogger(__name__)


def load_checkpoint() -> dict:
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE) as f:
            return json.load(f)
    return {}


def save_checkpoint(state: dict) -> None:
    os.makedirs(os.path.dirname(CHECKPOINT_FILE), exist_ok=True)
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(state, f, indent=2)


def reset() -> None:
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)
        log.info("Checkpoint reset.")
