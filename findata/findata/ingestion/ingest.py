"""
ingestion/ingest.py

Ingests all CF Export .xlsx files from a folder into a DuckDB database.

Usage:
    python -m ingestion.ingest --source /path/to/xlsx/folder --db data/findata.duckdb

Supports incremental upserts — re-run at any time when new files arrive.
Files are identified by RIC extracted from the workbook itself, not the filename.
"""

import os
import sys
import argparse
import logging
import duckdb
import pandas as pd
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).parent.parent))
from ingestion.parser import parse_file
from ingestion.aliases import ALIASES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger(__name__)

DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS facts (
    ric          VARCHAR,
    company_name VARCHAR,
    sheet        VARCHAR,
    section      VARCHAR,
    variable     VARCHAR,
    year         VARCHAR,
    value        DOUBLE,
    currency     VARCHAR,
    scaling      VARCHAR,
    PRIMARY KEY (ric, sheet, variable, year)
);

CREATE TABLE IF NOT EXISTS aliases (
    alias    VARCHAR PRIMARY KEY,
    variable VARCHAR
);

CREATE TABLE IF NOT EXISTS ingestion_log (
    filepath     VARCHAR PRIMARY KEY,
    ric          VARCHAR,
    company_name VARCHAR,
    rows_loaded  INTEGER,
    ingested_at  TIMESTAMP DEFAULT current_timestamp
);
"""


def setup_db(db_path: str) -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(db_path)
    con.execute(DB_SCHEMA)
    return con


def seed_aliases(con: duckdb.DuckDBPyConnection) -> None:
    existing = {r[0] for r in con.execute("SELECT alias FROM aliases").fetchall()}
    rows = [(k.upper(), v) for k, v in ALIASES.items() if k.upper() not in existing]
    if rows:
        con.executemany("INSERT OR IGNORE INTO aliases VALUES (?, ?)", rows)
        log.info("Seeded %d aliases", len(rows))


def ingest_file(con: duckdb.DuckDBPyConnection, filepath: str) -> None:
    already = con.execute(
        "SELECT ric FROM ingestion_log WHERE filepath = ?", [filepath]
    ).fetchone()
    if already:
        log.debug("Already ingested: %s", filepath)
        return

    log.info("Parsing: %s", filepath)
    try:
        df = parse_file(filepath)
    except Exception as exc:
        log.error("Failed to parse %s: %s", filepath, exc)
        return

    if df.empty:
        log.warning("No data extracted from %s", filepath)
        return

    ric = df["ric"].iloc[0]
    company = df["company_name"].iloc[0]

    # Delete existing rows for this RIC before re-inserting (full refresh per company)
    con.execute("DELETE FROM facts WHERE ric = ?", [ric])

    con.execute("INSERT OR REPLACE INTO facts SELECT * FROM df")

    con.execute(
        "INSERT OR REPLACE INTO ingestion_log VALUES (?, ?, ?, ?, current_timestamp)",
        [filepath, ric, company, len(df)],
    )

    log.info("  → %s (%s): %d rows", company, ric, len(df))


def ingest_folder(source_dir: str, db_path: str) -> None:
    xlsx_files = list(Path(source_dir).rglob("*.xlsx"))
    if not xlsx_files:
        log.warning("No .xlsx files found in %s", source_dir)
        return

    log.info("Found %d files to process", len(xlsx_files))
    con = setup_db(db_path)
    seed_aliases(con)

    for i, fp in enumerate(xlsx_files, 1):
        log.info("[%d/%d] %s", i, len(xlsx_files), fp.name)
        ingest_file(con, str(fp))

    con.close()
    log.info("Done. Database: %s", db_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest CF Export files into DuckDB")
    parser.add_argument("--source", required=True, help="Folder containing .xlsx files")
    parser.add_argument("--db",     default="data/findata.duckdb", help="DuckDB file path")
    args = parser.parse_args()

    os.makedirs(os.path.dirname(args.db) or ".", exist_ok=True)
    ingest_folder(args.source, args.db)
