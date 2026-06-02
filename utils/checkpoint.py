"""
checkpoint.py — Saves and loads pipeline progress so crashes are recoverable.

Progress is stored as a JSON file at the path defined in settings.CHECKPOINT_FILE.
Structure:
  {
    "completed": ["USA::AAPL.O", "USA::MSFT.O", ...],
    "failed":    {"USA::XYZ.N": "error message", ...}
  }
"""

import json
import os
from config.settings import CHECKPOINT_FILE


def _load() -> dict:
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r") as f:
            return json.load(f)
    return {"completed": [], "failed": {}}


def _save(state: dict):
    os.makedirs(os.path.dirname(CHECKPOINT_FILE), exist_ok=True)
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(state, f, indent=2)


def mark_done(country_code: str, ric: str):
    state = _load()
    key = f"{country_code}::{ric}"
    if key not in state["completed"]:
        state["completed"].append(key)
    state["failed"].pop(key, None)
    _save(state)


def mark_failed(country_code: str, ric: str, error: str):
    state = _load()
    key = f"{country_code}::{ric}"
    state["failed"][key] = error
    _save(state)


def is_done(country_code: str, ric: str) -> bool:
    state = _load()
    return f"{country_code}::{ric}" in state["completed"]


def summary() -> dict:
    state = _load()
    return {
        "completed": len(state["completed"]),
        "failed":    len(state["failed"]),
        "failed_list": state["failed"],
    }


def reset():
    """Delete checkpoint and start fresh."""
    if os.path.exists(CHECKPOINT_FILE):
        os.remove(CHECKPOINT_FILE)
