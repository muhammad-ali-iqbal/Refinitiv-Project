"""
run_pipeline.py — Entry point. Run this to start the pipeline.

Before running:
  1. Set your LSEG API key below (or export as LSEG_APP_KEY env variable).
  2. Make sure Eikon / LSEG Workspace desktop app is open and logged in.
  3. Adjust config/settings.py for output path and countries.

Install dependencies:
  pip install lseg-data openpyxl pandas
"""

import os
import sys

# ── Your LSEG / Eikon API key ─────────────────────────────────────────────────
# Generate one inside Eikon/Workspace: top-right menu → API → Create API key
# Or export the environment variable: export LSEG_APP_KEY="your_key_here"
LSEG_APP_KEY = "13435b03147b41f28829ac8f137e0f629d279125"

# ── Optional: run only a subset of countries for testing ─────────────────────
# Set to None to run all countries from config/settings.py
# Example: COUNTRIES_OVERRIDE = {"United States": "USA"}
COUNTRIES_OVERRIDE = None


# ── Run ───────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    if not LSEG_APP_KEY:
        print("ERROR: Set your LSEG API key in run_pipeline.py or the LSEG_APP_KEY env variable.")
        sys.exit(1)

    sys.path.insert(0, os.path.dirname(__file__))

    from pipeline.orchestrator import run

    print("Starting pipeline — make sure Eikon/Workspace is open and logged in.")
    print()
    run(app_key=LSEG_APP_KEY, countries=COUNTRIES_OVERRIDE)
