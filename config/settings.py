"""
settings.py — Central configuration for the Refinitiv pipeline.
Edit this file to control which countries, output path, and rate limits to use.
FINANCIAL_FIELDS has been removed — full standardised statements are now fetched
automatically via the TR.F. field namespace (see pipeline/fetcher.py).
"""

import os

# ── Output root ────────────────────────────────────────────────────────────────
# Change this to your manager's desktop path, e.g.:
#   Windows: r"C:\Users\Manager\Desktop\Data"
#   macOS:   "/Users/manager/Desktop/Data"
OUTPUT_ROOT = os.path.join(os.path.expanduser("~"), "Desktop", "Data")

# ── Countries to extract ───────────────────────────────────────────────────────
# Format: { "Folder name": "Refinitiv country code" }
COUNTRIES = {
    "United States":    "USA",
    "United Kingdom":   "GBR",
    "Germany":          "DEU",
    "France":           "FRA",
    "Japan":            "JPN",
    "China":            "CHN",
    "India":            "IND",
    "Brazil":           "BRA",
    "Australia":        "AUS",
    "Canada":           "CAN",
}

# ── Historical period ──────────────────────────────────────────────────────────
HISTORY_YEARS = 10
SDATE = f"-{HISTORY_YEARS}Y"
EDATE = "0"

# ── Statement fetch type ───────────────────────────────────────────────────────
# "IAS"  = IFRS / international standard (most non-US companies)
# "GAAp" = US GAAP
# "ORI"  = As-reported (original filing line items)
# "STD"  = Refinitiv standardised (normalised across all companies) ← recommended
STATEMENT_TYPE = "STD"

# ── Rate limiting ──────────────────────────────────────────────────────────────
BATCH_SIZE             = 50
DELAY_BETWEEN_BATCHES  = 1.5
DELAY_BETWEEN_COMPANIES = 0.5   # Slightly higher — now making 3 calls per company
MAX_RETRIES            = 3
RETRY_BACKOFF          = 5.0

# ── Checkpoint file ────────────────────────────────────────────────────────────
CHECKPOINT_FILE = os.path.join(OUTPUT_ROOT, "_pipeline_checkpoint.json")
