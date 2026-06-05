"""
config/settings.py — All tunable parameters for the pipeline.
Edit this file to control output path, countries, and rate limits.
"""

import os

# ── Output root ────────────────────────────────────────────────────────────────
OUTPUT_ROOT = os.path.join(os.path.expanduser("~"), "Desktop", "Data")

# ── Countries to extract ───────────────────────────────────────────────────────
# Format: { "Folder name": "ISO-2 country code for TR.ExchangeCountryCode" }
COUNTRIES = {
    "United States":  "US",
    ##"United Kingdom": "GB",
    ##"Germany":        "DE",
    ##"France":         "FR",
    ##"Japan":          "JP",
    ##"China":          "CN",
    ##"India":          "IN",
    ##"Brazil":         "BR",
    ##"Australia":      "AU",
    ##"Canada":         "CA",
}

# ── Historical period ──────────────────────────────────────────────────────────
HISTORY_YEARS = 10
SDATE = f"-{HISTORY_YEARS}Y"
EDATE = "0"

# ── Statement fetch type ───────────────────────────────────────────────────────
# "STD"  = Refinitiv standardised (normalised across all companies) ← recommended
# "IAS"  = IFRS / international standard
# "GAAP" = US GAAP
# "ORI"  = As-reported (original filing line items)
STATEMENT_TYPE = "STD"

# ── Rate limiting ──────────────────────────────────────────────────────────────
BATCH_SIZE              = 50
DELAY_BETWEEN_BATCHES   = 1.5
DELAY_BETWEEN_COMPANIES = 0.5
MAX_RETRIES             = 3
RETRY_BACKOFF           = 5.0

# ── Checkpoint file ────────────────────────────────────────────────────────────
CHECKPOINT_FILE = os.path.join(OUTPUT_ROOT, "_pipeline_checkpoint.json")
