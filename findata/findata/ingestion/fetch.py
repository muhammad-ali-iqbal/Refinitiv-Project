"""
ingestion/fetch.py

Fetches financial, valuation, ESG and consensus-estimates data from the
Refinitiv Eikon API and writes directly into the DuckDB facts table.
No Excel intermediate step — replaces the manual CF Export workflow.

Prerequisites
─────────────
  1. LSEG Workspace / Refinitiv Eikon desktop app must be open and signed in.
  2. pip install eikon
  3. Set EIKON_APP_KEY environment variable  OR  pass --app-key.

Usage
─────
  python -m ingestion.fetch --db data/findata.duckdb
  python -m ingestion.fetch --db data/findata.duckdb --index "0#.KSE" --reset
  python -m ingestion.fetch --db data/findata.duckdb --rics "PSO.PSX,LUCK.PSX"

Notes
─────
  • Requires Workspace to be running — the eikon package proxies through it.
  • TR. field codes are validated against Refinitiv's Data Item Browser.
    If a field returns no data, verify the exact code there.
  • PSX default index RIC is 0#.KSE (KSE Composite). For KSE-100 only,
    try 0#KSE100.PSX. Verify in Workspace → Screener if unsure.
  • Financial-statement values are returned in the company's native currency
    (PKR for most PSX companies) at Millions scale.
  • ESG data coverage starts ~2002; earlier years will return no values.
  • Estimates cover current + 2 forward fiscal years; historical snapshots
    go back as far as Refinitiv has stored consensus data.
"""

import os
import sys
import time
import logging
import argparse
from pathlib import Path

import duckdb
import pandas as pd
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

try:
    import eikon as ek
except ImportError:
    sys.exit("eikon package not found.  Run:  pip install eikon")

sys.path.insert(0, str(Path(__file__).parent.parent))
from ingestion.ingest import setup_db, seed_aliases

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
)
log = logging.getLogger(__name__)

# ─── Eikon connection ─────────────────────────────────────────────────────────

def connect_eikon(app_key: str | None) -> None:
    key = app_key or os.environ.get("EIKON_APP_KEY")
    if not key:
        sys.exit("Provide an Eikon app key via --app-key or the EIKON_APP_KEY env var.")
    ek.set_app_key(key)
    log.info("Eikon API key configured.")

# ─── Field catalogue ──────────────────────────────────────────────────────────
# Each entry: (tr_code, variable_name, sheet, section, scaling)
#
# variable_name intentionally matches the strings already used in aliases.py
# so existing app queries continue to work against API-sourced data.
#
# scaling: "Millions" for monetary statement values, "" for ratios / prices / scores.

FIELDS = [
    # ── Income Statement ──────────────────────────────────────────────────────
    ("TR.Revenue",              "Revenue from Business Activities - Total",                                                     "Income Statement", "Revenue",        "Millions"),
    ("TR.GrossProfit",          "Gross Profit - Industrials/Property - Total",                                                  "Income Statement", "Profitability",  "Millions"),
    ("TR.EBITDA",               "Earnings before Interest, Taxes, Depreciation & Amortization (EBITDA)",                       "Income Statement", "Profitability",  "Millions"),
    ("TR.EBIT",                 "Operating Profit before Non-Recurring Income/Expense",                                         "Income Statement", "Profitability",  "Millions"),
    ("TR.NetIncome",            "Income before Discontinued Operations & Extraordinary Items",                                   "Income Statement", "Net Income",     "Millions"),
    ("TR.EPSDilExclExtraItems", "EPS - Diluted - excluding Extraordinary Items Applicable to Common - Total",                   "Income Statement", "Per Share",      ""),

    # ── Balance Sheet ─────────────────────────────────────────────────────────
    ("TR.TotalAssets",          "Total Assets",                                                                                  "Balance Sheet",   "Assets",         "Millions"),
    ("TR.CashAndSTInvestments", "Cash & Cash Equivalents",                                                                       "Balance Sheet",   "Assets",         "Millions"),
    ("TR.TotalDebt",            "Debt - Total",                                                                                   "Balance Sheet",   "Liabilities",    "Millions"),
    ("TR.CommonEquity",         "Common Equity - Total",                                                                          "Balance Sheet",   "Equity",         "Millions"),

    # ── Cash Flow ─────────────────────────────────────────────────────────────
    ("TR.NetCashFromOperatingActivities", "Net Cash Flow from Operating Activities",                                             "Cash Flow",       "Operating",      "Millions"),
    ("TR.CapitalExpenditures",  "Capital Expenditures - Net - Cash Flow",                                                        "Cash Flow",       "Investing",      "Millions"),
    ("TR.FreeCashFlow",         "Free Cash Flow",                                                                                 "Cash Flow",       "Free Cash Flow", "Millions"),

    # ── Valuation ─────────────────────────────────────────────────────────────
    ("TR.PriceClose",           "Price Close (End of Period)",                                                                    "Valuation",       "Price",          ""),
    ("TR.MktCap",               "Market Capitalization",                                                                          "Valuation",       "Market",         "Millions"),
    ("TR.EnterpriseValue",      "Enterprise Value",                                                                               "Valuation",       "Market",         "Millions"),
    ("TR.PEInclExtraItems",     "Price to EPS - Diluted - excluding Extraordinary Items Applicable to Common - Total",            "Valuation",       "Multiples",      ""),
    ("TR.PriceToBVPerShare",    "Price to Book Value per Share - Issue Specific",                                                 "Valuation",       "Multiples",      ""),
    ("TR.PriceToTangBVPerShare","Price to Tangible Book Value per Share",                                                         "Valuation",       "Multiples",      ""),
    ("TR.PriceToRevPerShare",   "Price to Revenue from Business Activities - Total per Share",                                    "Valuation",       "Multiples",      ""),
    ("TR.PriceToCFPerShare",    "Price to Cash Flow per Share",                                                                   "Valuation",       "Multiples",      ""),
    ("TR.PriceToFCFPerShare",   "Price to Free Cash Flow per Share",                                                              "Valuation",       "Multiples",      ""),
    ("TR.EVToEBITDA",           "Enterprise Value to Earnings before Interest, Taxes, Depreciation & Amortization (EBITDA)",     "Valuation",       "EV Multiples",   ""),
    ("TR.EVToRevenue",          "Enterprise Value to Revenue from Business Activities - Total",                                   "Valuation",       "EV Multiples",   ""),
    ("TR.EVToCFO",              "Enterprise Value to Net Cash Flow from Operating Activities",                                    "Valuation",       "EV Multiples",   ""),
    ("TR.DivYield",             "Dividend Yield - Common Stock - Net - Issue Specific - %",                                       "Valuation",       "Dividends",      ""),
    ("TR.FCFYield",             "Free Cash Flow Yield - %",                                                                       "Valuation",       "Dividends",      ""),
    ("TR.PEGRatio",             "PE Growth Ratio",                                                                                "Valuation",       "Multiples",      ""),

    # ── Financial Ratios ──────────────────────────────────────────────────────
    ("TR.ROE",                  "Return on Average Common Equity - % (Income available to Common excluding Extraordinary Items)", "Financial Summary","Returns",        ""),
    ("TR.ROA",                  "Return on Average Total Assets - % (Income before Discontinued Operations & Extraordinary Items)","Financial Summary","Returns",       ""),
    ("TR.ROIC",                 "Return on Invested Capital - %",                                                                 "Financial Summary","Returns",        ""),
    ("TR.GrossProfitMarginPct", "Gross Profit Margin - %",                                                                        "Financial Summary","Margins",        ""),
    ("TR.EBITDAMarginPct",      "EBITDA Margin - %",                                                                              "Financial Summary","Margins",        ""),
    ("TR.OperatingMarginPct",   "Operating Margin - %",                                                                           "Financial Summary","Margins",        ""),
    ("TR.NetProfitMarginPct",   "Net Margin - %",                                                                                 "Financial Summary","Margins",        ""),

    # ── ESG ───────────────────────────────────────────────────────────────────
    ("TR.TRESGScore",                    "ESG Score",                               "ESG","Combined",    ""),
    ("TR.TRESGCScore",                   "ESG Combined Score (with Controversies)", "ESG","Combined",    ""),
    ("TR.EnvironmentPillarScore",        "Environment Pillar Score",                "ESG","Pillars",     ""),
    ("TR.SocialPillarScore",             "Social Pillar Score",                     "ESG","Pillars",     ""),
    ("TR.GovernancePillarScore",         "Governance Pillar Score",                 "ESG","Pillars",     ""),
    ("TR.ESGResourceUseScore",           "Resource Use Score",                      "ESG","Environment", ""),
    ("TR.ESGEmissionsScore",             "Emissions Score",                         "ESG","Environment", ""),
    ("TR.ESGInnovationScore",            "Innovation Score",                        "ESG","Environment", ""),
    ("TR.ESGWorkforceScore",             "Workforce Score",                         "ESG","Social",      ""),
    ("TR.ESGHumanRightsScore",           "Human Rights Score",                      "ESG","Social",      ""),
    ("TR.ESGCommunityScore",             "Community Score",                         "ESG","Social",      ""),
    ("TR.ESGProductResponsibilityScore", "Product Responsibility Score",            "ESG","Social",      ""),
    ("TR.ESGManagementScore",            "Management Score",                        "ESG","Governance",  ""),
    ("TR.ESGShareholdersScore",          "Shareholders Score",                      "ESG","Governance",  ""),
    ("TR.ESGCSRStrategyScore",           "CSR Strategy Score",                      "ESG","Governance",  ""),

    # ── Estimates (consensus) ─────────────────────────────────────────────────
    ("TR.RevenueMean",     "Revenue Estimate (Consensus Mean)",    "Estimates","Income Statement","Millions"),
    ("TR.EBITDAMean",      "EBITDA Estimate (Consensus Mean)",     "Estimates","Income Statement","Millions"),
    ("TR.NetIncomeMean",   "Net Income Estimate (Consensus Mean)", "Estimates","Income Statement","Millions"),
    ("TR.EPSMean",         "EPS Estimate (Consensus Mean)",        "Estimates","Per Share",       ""),
    ("TR.PriceTargetMean", "Price Target (Consensus Mean)",        "Estimates","Price",           ""),
]

# ─── Fetch config ─────────────────────────────────────────────────────────────

BATCH_SIZE  = 50     # RICs per API call — stays well under the 10k data-point cap
REQUEST_GAP = 0.5    # seconds between calls to respect rate limits
RETRY_MAX   = 3
RETRY_DELAY = 10     # seconds before retry on EikonError
START_DATE  = "2000-01-01"
END_DATE    = "2025-12-31"

# ─── Extra schema (added alongside existing tables) ───────────────────────────

FETCH_LOG_DDL = """
CREATE TABLE IF NOT EXISTS fetch_log (
    ric        VARCHAR,
    field_key  VARCHAR,
    fetched_at TIMESTAMP DEFAULT current_timestamp,
    rows_loaded INTEGER,
    PRIMARY KEY (ric, field_key)
);
"""

# ─── Universe ─────────────────────────────────────────────────────────────────

def get_index_rics(index_ric: str) -> list[str]:
    """Return all equity RICs in the given Eikon index."""
    log.info("Fetching universe from index: %s", index_ric)
    df, err = ek.get_data(index_ric, ["TR.RIC", "TR.CommonName"])
    if err:
        log.warning("Index fetch warning: %s", err)
    if df is None or df.empty:
        sys.exit(
            f"No RICs returned for index '{index_ric}'.\n"
            "Common PSX codes to try: 0#.KSE  /  0#KSE100.PSX  /  0#.PSX\n"
            "Verify in Workspace → Search → Screener."
        )
    rics = [r for r in df["Instrument"].dropna().tolist() if not str(r).startswith(".")]
    log.info("Universe: %d instruments", len(rics))
    return rics

# ─── Metadata ─────────────────────────────────────────────────────────────────

def fetch_metadata(rics: list[str]) -> dict[str, dict]:
    """
    Fetch company name and reporting currency for every RIC.
    Returns {ric: {company_name, currency}}.
    """
    meta: dict[str, dict] = {}
    total = len(rics)
    for i in range(0, total, BATCH_SIZE):
        batch = rics[i : i + BATCH_SIZE]
        log.info("  metadata batch %d/%d", i // BATCH_SIZE + 1, -(-total // BATCH_SIZE))
        try:
            df, _ = ek.get_data(batch, ["TR.CommonName", "TR.Currency"])
            for _, row in df.iterrows():
                ric = row["Instrument"]
                meta[ric] = {
                    "company_name": str(row.get("Company Common Name") or ""),
                    "currency":     str(row.get("Currency") or ""),
                }
        except Exception as exc:
            log.warning("  metadata batch failed: %s", exc)
        time.sleep(REQUEST_GAP)
    return meta

# ─── Single-field fetch ───────────────────────────────────────────────────────

def _call_eikon(instruments, fields, params):
    for attempt in range(1, RETRY_MAX + 1):
        try:
            df, err = ek.get_data(instruments, fields, params)
            if err:
                log.debug("Eikon warning: %s", err)
            return df
        except ek.EikonError as exc:
            log.warning("EikonError (attempt %d/%d): %s", attempt, RETRY_MAX, exc)
            if attempt < RETRY_MAX:
                time.sleep(RETRY_DELAY)
    return None


def fetch_field(rics: list[str], tr_code: str) -> pd.DataFrame:
    """
    Fetch one TR field for all RICs across 2000-2025 (annual frequency).
    Returns a long DataFrame with columns: ric | year | value
    """
    date_field = f"{tr_code}.calcdate"
    params = {"SDate": START_DATE, "EDate": END_DATE, "FRQ": "FY"}
    rows = []
    total = len(rics)

    for i in range(0, total, BATCH_SIZE):
        batch = rics[i : i + BATCH_SIZE]
        df = _call_eikon(batch, [tr_code, date_field], params)
        time.sleep(REQUEST_GAP)

        if df is None or df.empty:
            continue

        cols = df.columns.tolist()
        if len(cols) < 2:
            continue

        # Positional: col 0 = Instrument, col 1 = value, col 2 = Calc Date
        val_col  = cols[1]
        date_col = cols[2] if len(cols) > 2 else None

        for _, row in df.iterrows():
            raw_val = row[val_col]
            if pd.isna(raw_val):
                continue
            try:
                value = float(raw_val)
            except (ValueError, TypeError):
                continue

            year = None
            if date_col and not pd.isna(row.get(date_col)):
                try:
                    year = str(pd.to_datetime(row[date_col]).year)
                except Exception:
                    pass
            if not year:
                continue

            rows.append({"ric": row["Instrument"], "year": year, "value": value})

    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["ric", "year", "value"])

# ─── Main fetch loop ──────────────────────────────────────────────────────────

def _field_key(tr_code: str) -> str:
    return tr_code  # used as fetch_log.field_key


def _already_fetched(con: duckdb.DuckDBPyConnection, ric: str, tr_code: str) -> bool:
    return con.execute(
        "SELECT 1 FROM fetch_log WHERE ric=? AND field_key=?", [ric, _field_key(tr_code)]
    ).fetchone() is not None


def fetch_all(
    rics: list[str],
    meta: dict[str, dict],
    con: duckdb.DuckDBPyConnection,
    reset: bool,
) -> None:
    con.execute(FETCH_LOG_DDL)

    if reset:
        log.info("--reset: clearing fetch_log for %d RICs", len(rics))
        con.executemany("DELETE FROM fetch_log WHERE ric=?", [[r] for r in rics])

    total = len(FIELDS)
    for idx, (tr_code, variable, sheet, section, scaling) in enumerate(FIELDS, 1):
        log.info("[%d/%d]  %-40s  %s", idx, total, tr_code, variable[:60])

        pending = [r for r in rics if not _already_fetched(con, r, tr_code)]
        if not pending:
            log.info("  all RICs already fetched — skipping")
            continue

        raw = fetch_field(pending, tr_code)
        if raw.empty:
            log.warning("  no data returned for %s", tr_code)
            continue

        raw["variable"]     = variable
        raw["sheet"]        = sheet
        raw["section"]      = section
        raw["scaling"]      = scaling
        raw["company_name"] = raw["ric"].map(lambda r: meta.get(r, {}).get("company_name", ""))
        raw["currency"]     = raw["ric"].map(lambda r: meta.get(r, {}).get("currency", ""))

        # Eikon sometimes returns multiple rows for the same fiscal year (restatements).
        # Keep the last occurrence — it's the most recent revision.
        raw = raw.drop_duplicates(subset=["ric", "year"], keep="last")

        returned_rics = raw["ric"].unique().tolist()

        # Delete stale rows for exactly the (ric, variable, sheet) tuples we are about to replace
        con.execute(
            "DELETE FROM facts WHERE variable=? AND sheet=? AND ric IN (SELECT DISTINCT ric FROM raw)",
            [variable, sheet],
        )
        con.execute(
            "INSERT INTO facts "
            "SELECT ric, company_name, sheet, section, variable, year, value, currency, scaling "
            "FROM raw"
        )

        con.executemany(
            "INSERT OR REPLACE INTO fetch_log VALUES (?, ?, current_timestamp, ?)",
            [
                (r, _field_key(tr_code), int((raw["ric"] == r).sum()))
                for r in returned_rics
            ],
        )
        log.info("  → %d rows  |  %d RICs", len(raw), len(returned_rics))

    log.info("Fetch complete.")

# ─── CLI ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pull Refinitiv data into DuckDB (no Excel step)."
    )
    parser.add_argument("--db",      default="data/findata.duckdb",
                        help="DuckDB file path (default: data/findata.duckdb)")
    parser.add_argument("--index",   default="0#.KSE",
                        help="Eikon index RIC for the universe (default: 0#.KSE for PSX)")
    parser.add_argument("--rics",    default="",
                        help="Comma-separated RICs; bypasses --index when provided")
    parser.add_argument("--app-key", default=None,
                        help="Eikon app key; falls back to EIKON_APP_KEY env var")
    parser.add_argument("--reset",   action="store_true",
                        help="Re-fetch all fields even if already in fetch_log")
    args = parser.parse_args()

    connect_eikon(args.app_key)

    if args.rics:
        rics = [r.strip() for r in args.rics.split(",") if r.strip()]
        log.info("Using explicit RIC list: %d instruments", len(rics))
    else:
        rics = get_index_rics(args.index)

    os.makedirs(os.path.dirname(args.db) or ".", exist_ok=True)
    con = setup_db(args.db)
    seed_aliases(con)

    log.info("Fetching company metadata…")
    meta = fetch_metadata(rics)

    fetch_all(rics, meta, con, reset=args.reset)
    con.close()
    log.info("Done. Database: %s", args.db)


if __name__ == "__main__":
    main()
