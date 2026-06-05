"""
pipeline/fetcher.py — All LSEG Data API calls with retry logic.

This is the ONLY file that imports lseg_data. Everything else in the pipeline
is API-agnostic. To swap data providers, only this file needs changing.

Migration note: previously used the `eikon` package. Now uses `lseg-data`,
LSEG's actively maintained replacement. Key differences:
  - `import lseg.data as ld` instead of `import eikon as ek`
  - Session opened via `ld.open_session()` instead of `ek.set_app_key()`
  - `ld.get_data(...)` replaces `ek.get_data(...)` — returns a DataFrame, not a (df, err) tuple
  - `ld.get_symbology(...)` replaces `ek.get_symbology(...)`
  - Error type is `lseg.data.errors.LDError` (still has .code attribute)
"""

import time
import logging
import pandas as pd
import lseg.data as ld
from lseg.data.errors import LDError

from config.settings import (
    STATEMENT_TYPE,
    SDATE,
    EDATE,
    BATCH_SIZE,
    DELAY_BETWEEN_BATCHES,
    MAX_RETRIES,
    RETRY_BACKOFF,
)

log = logging.getLogger(__name__)

# ── Statement field definitions ────────────────────────────────────────────────
# Each tuple: (TR field code, display label, Excel number format)
# All fields use Refinitiv's TR.F.* standardised namespace.

INCOME_STATEMENT_FIELDS = [
    ("TR.Revenue",                  "Total Revenue",            "#,##0"),
    ("TR.GrossProfit",              "Gross Profit",             "#,##0"),
    ("TR.EBIT",                     "Operating Income (EBIT)",  "#,##0"),
    ("TR.EBITDA",                   "EBITDA",                   "#,##0"),
    ("TR.NetIncome",                "Net Income",               "#,##0"),
    ("TR.DepreciationAmortization", "D&A",                      "#,##0"),
    ("TR.InterestExpense",          "Interest Expense",         "#,##0"),
]

BALANCE_SHEET_FIELDS = [
    ("TR.CashAndSTInvestments",     "Cash & ST Investments",    "#,##0"),
    ("TR.TotalCurrentAssets",       "Total Current Assets",     "#,##0"),
    ("TR.TotalAssets",              "Total Assets",             "#,##0"),
    ("TR.TotalCurrentLiabilities",  "Total Current Liabilities","#,##0"),
    ("TR.LTDebt",                   "Long-term Debt",           "#,##0"),
    ("TR.TotalDebt",                "Total Debt",               "#,##0"),
    ("TR.TotalLiabilities",         "Total Liabilities",        "#,##0"),
    ("TR.TotalEquity",              "Total Equity",             "#,##0"),
    ("TR.RetainedEarnings",         "Retained Earnings",        "#,##0"),
    ("TR.BookValuePerShare",        "Book Value Per Share",     "0.00"),
]

CASH_FLOW_FIELDS = [
    ("TR.FreeCashFlow",             "Free Cash Flow",           "#,##0"),
    ("TR.NetChangeInCash",          "Net Change in Cash",       "#,##0"),
]

# Combined dict — used by orchestrator and excel_writer
STATEMENTS = {
    "Income Statement": INCOME_STATEMENT_FIELDS,
    "Balance Sheet":    BALANCE_SHEET_FIELDS,
    "Cash Flow":        CASH_FLOW_FIELDS,
}


# ── Session management ─────────────────────────────────────────────────────────

def open_session(app_key: str) -> None:
    """
    Open an lseg-data session using the desktop (Eikon/Workspace) proxy.
    Call once at pipeline startup before any data fetches.

    lseg-data equivalent of: eikon.set_app_key(app_key)
    """
    ld.open_session(
        name="desktop.workspace",
        app_key=app_key,
    )
    log.info("lseg-data session opened (desktop proxy)")


def close_session() -> None:
    """Close the lseg-data session. Call at pipeline shutdown."""
    ld.close_session()
    log.info("lseg-data session closed")


# ── Company discovery ──────────────────────────────────────────────────────────

def get_companies_for_country(country_code: str) -> list[dict]:
    """
    Return all active, primary-listed equities for a country.

    Args:
        country_code: ISO-2 code for TR.ExchangeCountryCode, e.g. "US", "GB"

    Returns:
        List of {"ric": str, "name": str} dicts.
    """
    screen_expr = (
        f'SCREEN(U(IN(Equity(active,public,primary))), '
        f'IN(TR.ExchangeCountryCode,"{country_code}"), '
        f'CURN=USD)'
    )

    results = []
    offset = 0

    while True:
        try:
            df = ld.get_data(
                universe=screen_expr,
                fields=["TR.CommonName", "TR.RIC"],
                parameters={"SDate": "0", "EDate": "0"},
            )
        except LDError as exc:
            log.error("Screening error for %s (code %s): %s", country_code, exc.code, exc)
            break

        if df is None or df.empty:
            break

        for _, row in df.iterrows():
            ric  = str(row.get("RIC",  "")).strip()
            name = str(row.get("Company Common Name", "")).strip()
            if ric and name:
                results.append({"ric": ric, "name": name})

        if len(df) < BATCH_SIZE:
            break

        offset += BATCH_SIZE
        time.sleep(DELAY_BETWEEN_BATCHES)

    log.info("Found %d companies for %s", len(results), country_code)
    return results


# ── Financial data fetch ───────────────────────────────────────────────────────

def _fetch_statement(
    ric: str,
    fields: list[tuple],
    statement_type: str,
    sdate: str,
    edate: str,
) -> pd.DataFrame:
    """
    Fetch one financial statement for a single RIC.

    Returns a DataFrame with:
        - Index: display labels (e.g. "Total Revenue")
        - Columns: fiscal year end dates (YYYY-MM-DD strings)

    Note: lseg-data returns one row per fiscal year (long format).
    We pivot to wide format using the .date sub-field for column headers.
    ReportingType and Period parameters are not supported in this API version.
    """
    field_codes  = [f[0] for f in fields]
    field_labels = [f[1] for f in fields]

    # TR.F.PeriodEndDate returns fiscal year end dates alongside TR.* value fields
    params = {
        "SDate": sdate,
        "EDate": edate,
        "Scale": 6,   # Millions
    }

    df = ld.get_data(
        universe=[ric],
        fields=field_codes + ["TR.F.PeriodEndDate"],
        parameters=params,
    )

    if df is None or df.empty:
        return pd.DataFrame()

    df = df.drop(columns=["Instrument"], errors="ignore")

    if df.empty or len(df.columns) < 2:
        return pd.DataFrame()

    # API returns columns in request order: [field1, ..., fieldN, "Period End Date"]
    # Rename positionally since display names vary by API version
    df.columns = field_labels + ["Date"]

    # Pivot to wide format: index = labels, columns = fiscal year dates
    df = df.set_index("Date").T
    df.index.name = None
    df.columns = [str(c)[:10] for c in df.columns]

    return df


def get_financials(ric: str) -> dict[str, pd.DataFrame]:
    """
    Fetch all three financial statements for a single RIC with retry logic.

    Returns:
        Dict keyed by statement name (matching STATEMENTS keys), each value
        a DataFrame with line items as rows and fiscal years as columns.
        Returns empty DataFrames on failure.
    """
    from config.settings import SDATE, EDATE, STATEMENT_TYPE

    output = {name: pd.DataFrame() for name in STATEMENTS}

    for stmt_name, fields in STATEMENTS.items():
        attempt = 0
        backoff = RETRY_BACKOFF

        while attempt < MAX_RETRIES:
            try:
                df = _fetch_statement(ric, fields, STATEMENT_TYPE, SDATE, EDATE)
                output[stmt_name] = df
                break

            except LDError as exc:
                attempt += 1
                if exc.code in (400_3001, "400.3001"):   # rate limit
                    log.warning(
                        "Rate limit hit for %s / %s (attempt %d). Waiting %.1fs.",
                        ric, stmt_name, attempt, backoff,
                    )
                    time.sleep(backoff)
                    backoff *= 2
                else:
                    log.error(
                        "LDError %s for %s / %s: %s",
                        exc.code, ric, stmt_name, exc,
                    )
                    break

            except Exception as exc:
                attempt += 1
                log.warning(
                    "Unexpected error for %s / %s (attempt %d): %s",
                    ric, stmt_name, attempt, exc,
                )
                time.sleep(backoff)
                backoff *= 2

    return output
