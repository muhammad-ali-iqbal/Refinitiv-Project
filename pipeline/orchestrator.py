"""
pipeline/orchestrator.py — Drives the full pipeline loop.

For each country → get company list → for each company → fetch financials → write Excel.
Handles checkpointing, logging, and per-company error isolation.
"""

import os
import time
import logging

from config.settings import (
    OUTPUT_ROOT,
    COUNTRIES,
    DELAY_BETWEEN_COMPANIES,
    DELAY_BETWEEN_BATCHES,
)
from pipeline import fetcher
from pipeline.excel_writer import write_workbook
from utils.checkpoint import load_checkpoint, save_checkpoint
from utils.logger import setup_logger

log = logging.getLogger(__name__)


def _index_path(country_folder: str) -> str:
    return os.path.join(OUTPUT_ROOT, country_folder, "_Index.xlsx")


def _company_path(country_folder: str, company_name: str) -> str:
    safe_name = "".join(c for c in company_name if c not in r'\/:*?"<>|')[:80]
    return os.path.join(OUTPUT_ROOT, country_folder, safe_name, f"{safe_name}.xlsx")


def run(app_key: str, countries: dict | None = None) -> None:
    """
    Main pipeline entry point.

    Args:
        app_key:   LSEG / Eikon API key (40 characters).
        countries: Override dict; uses settings.COUNTRIES if None.
    """
    setup_logger(OUTPUT_ROOT)
    log.info("Pipeline starting")

    fetcher.open_session(app_key)

    target_countries = countries or COUNTRIES
    checkpoint = load_checkpoint()

    try:
        for country_name, country_code in target_countries.items():
            log.info("=== %s (%s) ===", country_name, country_code)

            companies = fetcher.get_companies_for_country(country_code)
            if not companies:
                log.warning("No companies found for %s — skipping", country_name)
                continue

            # TEST LIMIT — remove this line for a full run
            companies = companies[:5]

            # Write _Index.xlsx
            import pandas as pd
            index_df = pd.DataFrame(companies)
            index_path = _index_path(country_name)
            os.makedirs(os.path.dirname(index_path), exist_ok=True)
            index_df.to_excel(index_path, index=False)
            log.info("Index written: %s (%d companies)", index_path, len(companies))

            time.sleep(DELAY_BETWEEN_BATCHES)

            for company in companies:
                ric  = company["ric"]
                name = company["name"]
                out_path = _company_path(country_name, name)

                if checkpoint.get(ric) == "done":
                    log.debug("Skip (already done): %s", ric)
                    continue

                try:
                    statements = fetcher.get_financials(ric)
                    write_workbook(out_path, name, statements)
                    checkpoint[ric] = "done"
                    save_checkpoint(checkpoint)

                except Exception as exc:
                    log.error("Failed %s (%s): %s", name, ric, exc)
                    checkpoint[ric] = "failed"
                    save_checkpoint(checkpoint)

                time.sleep(DELAY_BETWEEN_COMPANIES)

    finally:
        fetcher.close_session()
        log.info("Pipeline finished")
