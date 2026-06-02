"""
run_pipeline.py — Entry point. Run this file to start the pipeline.

Usage:
  python run_pipeline.py

Before running:
  1. Set YOUR_EIKON_APP_KEY below (or export it as an environment variable).
  2. Make sure Eikon/Workspace desktop app is open and logged in.
  3. Adjust config/settings.py to set OUTPUT_ROOT and select countries.

Install dependencies first:
  pip install eikon openpyxl pandas
"""

import os
import sys

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION — Edit these before running
# ─────────────────────────────────────────────────────────────────────────────

# Your Eikon API key (40 characters).
# Find it in: Eikon → top-right menu → API → Create/View API key
# Alternatively, set the environment variable EIKON_APP_KEY.
EIKON_APP_KEY = os.environ.get("EIKON_APP_KEY", "PASTE_YOUR_40_CHAR_KEY_HERE")

# Optional: run only a subset of countries for testing.
# Set to None to run all countries defined in config/settings.py.
# Example: COUNTRIES_OVERRIDE = {"United States": "USA", "United Kingdom": "GBR"}
COUNTRIES_OVERRIDE = None


# ─────────────────────────────────────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if EIKON_APP_KEY == "PASTE_YOUR_40_CHAR_KEY_HERE":
        print("ERROR: Please set your Eikon API key in run_pipeline.py or the EIKON_APP_KEY environment variable.")
        sys.exit(1)

    # Add project root to path so relative imports work
    sys.path.insert(0, os.path.dirname(__file__))

    from pipeline.orchestrator import run

    print("Starting Refinitiv data pipeline…")
    print("Make sure Eikon/Workspace is open and logged in before continuing.")
    print()

    run(app_key=EIKON_APP_KEY, countries=COUNTRIES_OVERRIDE)
