"""
orchestrator.py — Drives the full pipeline from country list → Excel files.

Run order per country:
  1. Fetch company list (RIC codes + names)
  2. Fetch summary batch → write _Index.xlsx
  3. For each company (skipping completed via checkpoint):
       a. get_all_statements()  → Income Statement, Balance Sheet, Cash Flow DataFrames
       b. write_company_workbook() → 4-sheet Excel file
       c. mark_done()

Usage:
  from pipeline.orchestrator import run
  run(app_key="YOUR_EIKON_APP_KEY")
"""

import os
import time

from config.settings import COUNTRIES, OUTPUT_ROOT, DELAY_BETWEEN_COMPANIES
from pipeline.fetcher      import (init_eikon, get_companies_for_country,
                                   get_all_statements, get_summary_batch, STATEMENTS)
from pipeline.excel_writer import write_company_workbook, write_country_index
from utils.checkpoint      import mark_done, mark_failed, is_done, summary as ckpt_summary
from utils.logger          import get_logger

log = get_logger(__name__)


def _make_country_folder(country_name: str) -> str:
    safe = country_name.replace("/", "-").strip()
    path = os.path.join(OUTPUT_ROOT, safe)
    os.makedirs(path, exist_ok=True)
    return path


def run(app_key: str, countries: dict | None = None):
    init_eikon(app_key)

    target_countries = countries or COUNTRIES
    total_written = total_skipped = total_failed = 0

    for country_name, country_code in target_countries.items():
        log.info(f"{'─'*60}")
        log.info(f"COUNTRY: {country_name} ({country_code})")
        log.info(f"{'─'*60}")

        country_folder = _make_country_folder(country_name)

        # ── Company list ───────────────────────────────────────────────────────
        try:
            companies = get_companies_for_country(country_code)
        except Exception as e:
            log.error(f"Failed to get company list for {country_name}: {e}")
            continue

        if not companies:
            log.warning(f"No companies found for {country_name}. Skipping.")
            continue

        rics = [c["ric"] for c in companies]

        # ── Country index ──────────────────────────────────────────────────────
        log.info(f"Building country index for {len(rics)} companies…")
        try:
            summary_df = get_summary_batch(rics)
            write_country_index(country_name, country_folder, summary_df)
        except Exception as e:
            log.warning(f"Could not write country index for {country_name}: {e}")

        # ── Per-company workbooks ──────────────────────────────────────────────
        log.info(f"Starting per-company extraction ({len(companies)} companies)…")

        for i, company in enumerate(companies, start=1):
            ric  = company["ric"]
            name = company["name"]

            if is_done(country_code, ric):
                log.debug(f"  [{i}/{len(companies)}] SKIP: {name} ({ric})")
                total_skipped += 1
                continue

            log.info(f"  [{i}/{len(companies)}] {name} ({ric})")

            try:
                statements = get_all_statements(ric)
                write_company_workbook(
                    ric=ric,
                    company_name=name,
                    statements=statements,
                    fields_defs=STATEMENTS,
                    country_folder=country_folder,
                )
                mark_done(country_code, ric)
                total_written += 1
            except Exception as e:
                log.error(f"  FAILED {ric}: {e}")
                mark_failed(country_code, ric, str(e))
                total_failed += 1

            time.sleep(DELAY_BETWEEN_COMPANIES)

        log.info(f"Finished {country_name}.")

    ckpt = ckpt_summary()
    log.info(f"\n{'═'*60}")
    log.info(f"PIPELINE COMPLETE")
    log.info(f"  Written this run : {total_written}")
    log.info(f"  Skipped (cached) : {total_skipped}")
    log.info(f"  Failed this run  : {total_failed}")
    log.info(f"  Total ever done  : {ckpt['completed']}")
    log.info(f"  Total ever failed: {ckpt['failed']}")
    if ckpt["failed_list"]:
        log.info("  Failed companies:")
        for key, err in ckpt["failed_list"].items():
            log.info(f"    {key}: {err}")
    log.info(f"{'═'*60}")
