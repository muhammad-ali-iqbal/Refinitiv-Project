"""
fetcher.py — All Eikon API calls with rate-limit-aware retry logic.

Fetches full standardised financial statements using Refinitiv's TR.F. namespace
rather than individual field codes. Each statement is returned as a DataFrame
with line items as rows and fiscal years as columns.

Public API:
  init_eikon(app_key)
  get_companies_for_country(country_code)  → list[dict]
  get_all_statements(ric)                  → dict[str, pd.DataFrame]
  get_summary_batch(rics)                  → pd.DataFrame
"""

import time
import eikon as ek
import pandas as pd

from config.settings import (
    SDATE, EDATE, STATEMENT_TYPE,
    BATCH_SIZE, DELAY_BETWEEN_BATCHES,
    MAX_RETRIES, RETRY_BACKOFF,
)
from utils.logger import get_logger

log = get_logger(__name__)


# ── Statement definitions ──────────────────────────────────────────────────────
# Each entry: (sheet_title, TR.F. report_type, list of (field_code, label, fmt))
#
# Refinitiv TR.F. standardised fields cover the full statement — every line item
# Refinitiv normalises across all companies, regardless of filing standard.
# Field reference: Eikon → F1 → Data Item Browser → Financial Statements → Standardized

INCOME_STATEMENT_FIELDS = [
    # ── Revenue
    ("TR.F.TotRevenue",               "Total Revenue",                    "#,##0"),
    ("TR.F.NetRevenue",               "Net Revenue",                      "#,##0"),
    ("TR.F.OtherRevenue",             "Other Revenue",                    "#,##0"),
    # ── Cost & Gross Profit
    ("TR.F.CostRevenue",              "Cost of Revenue",                  "#,##0"),
    ("TR.F.GrosProfit",               "Gross Profit",                     "#,##0"),
    # ── Operating Expenses
    ("TR.F.SellingGenAdminExp",       "SG&A Expenses",                    "#,##0"),
    ("TR.F.ResDevExp",                "R&D Expenses",                     "#,##0"),
    ("TR.F.DepAmortExp",              "Depreciation & Amortisation",      "#,##0"),
    ("TR.F.OtherOperExp",             "Other Operating Expenses",         "#,##0"),
    ("TR.F.TotOperExp",               "Total Operating Expenses",         "#,##0"),
    # ── Operating Income
    ("TR.F.OperInc",                  "Operating Income (EBIT)",          "#,##0"),
    ("TR.F.EBITDA",                   "EBITDA",                           "#,##0"),
    # ── Non-Operating
    ("TR.F.InterestExpense",          "Interest Expense",                 "#,##0"),
    ("TR.F.InterestIncome",           "Interest Income",                  "#,##0"),
    ("TR.F.OtherNonOperInc",          "Other Non-Operating Income",       "#,##0"),
    ("TR.F.NonOperIncLoss",           "Total Non-Operating Income",       "#,##0"),
    # ── Pre-tax & Tax
    ("TR.F.PretaxInc",                "Pre-Tax Income",                   "#,##0"),
    ("TR.F.IncomeTaxExp",             "Income Tax Expense",               "#,##0"),
    ("TR.F.EffTaxRate",               "Effective Tax Rate",               "0.0%"),
    # ── Net Income
    ("TR.F.MinorityIntInc",           "Minority Interest",                "#,##0"),
    ("TR.F.NetInc",                   "Net Income",                       "#,##0"),
    ("TR.F.NetIncAvailToComShr",      "Net Income to Common",             "#,##0"),
    # ── Per Share
    ("TR.F.EPS",                      "EPS (Basic)",                      "#,##0.00"),
    ("TR.F.EPSDiluted",               "EPS (Diluted)",                    "#,##0.00"),
    ("TR.F.DivPerShare",              "Dividends Per Share",              "#,##0.00"),
    ("TR.F.WAvgDilutedSharesOut",     "Diluted Shares Outstanding",       "#,##0"),
]

BALANCE_SHEET_FIELDS = [
    # ── Current Assets
    ("TR.F.CashEquiv",                "Cash & Equivalents",               "#,##0"),
    ("TR.F.ShortTermInv",             "Short-Term Investments",           "#,##0"),
    ("TR.F.TotCashAndShortTermInv",   "Total Cash & ST Investments",      "#,##0"),
    ("TR.F.NetReceiv",                "Net Receivables",                  "#,##0"),
    ("TR.F.TotInventory",             "Inventories",                      "#,##0"),
    ("TR.F.OtherCurrAssets",          "Other Current Assets",             "#,##0"),
    ("TR.F.TotCurrAssets",            "Total Current Assets",             "#,##0"),
    # ── Non-Current Assets
    ("TR.F.NetPPE",                   "Net PP&E",                         "#,##0"),
    ("TR.F.Goodwill",                 "Goodwill",                         "#,##0"),
    ("TR.F.IntangibleAssets",         "Intangible Assets",                "#,##0"),
    ("TR.F.LongTermInv",              "Long-Term Investments",            "#,##0"),
    ("TR.F.OtherNonCurrAssets",       "Other Non-Current Assets",         "#,##0"),
    ("TR.F.TotNonCurrAssets",         "Total Non-Current Assets",         "#,##0"),
    # ── Total Assets
    ("TR.F.TotAssets",                "Total Assets",                     "#,##0"),
    # ── Current Liabilities
    ("TR.F.AccountsPayable",          "Accounts Payable",                 "#,##0"),
    ("TR.F.ShortTermDebt",            "Short-Term Debt",                  "#,##0"),
    ("TR.F.DeferredRevenue",          "Deferred Revenue",                 "#,##0"),
    ("TR.F.OtherCurrLiab",            "Other Current Liabilities",        "#,##0"),
    ("TR.F.TotCurrLiab",              "Total Current Liabilities",        "#,##0"),
    # ── Non-Current Liabilities
    ("TR.F.LongTermDebt",             "Long-Term Debt",                   "#,##0"),
    ("TR.F.DeferredTaxLiab",          "Deferred Tax Liabilities",         "#,##0"),
    ("TR.F.OtherNonCurrLiab",         "Other Non-Current Liabilities",    "#,##0"),
    ("TR.F.TotNonCurrLiab",           "Total Non-Current Liabilities",    "#,##0"),
    # ── Total Liabilities & Equity
    ("TR.F.TotLiab",                  "Total Liabilities",                "#,##0"),
    ("TR.F.MinorityInterest",         "Minority Interest",                "#,##0"),
    ("TR.F.CommonStock",              "Common Stock",                     "#,##0"),
    ("TR.F.RetainedEarnings",         "Retained Earnings",                "#,##0"),
    ("TR.F.TotEquity",                "Total Equity",                     "#,##0"),
    ("TR.F.TotLiabAndEquity",         "Total Liabilities & Equity",       "#,##0"),
    # ── Derived
    ("TR.F.TotDebt",                  "Total Debt",                       "#,##0"),
    ("TR.F.NetDebt",                  "Net Debt",                         "#,##0"),
    ("TR.F.BookValuePerShare",        "Book Value Per Share",             "#,##0.00"),
]

CASH_FLOW_FIELDS = [
    # ── Operating
    ("TR.F.NetIncomeStartingLine",    "Net Income (starting line)",       "#,##0"),
    ("TR.F.DepAmortCF",               "D&A (add-back)",                   "#,##0"),
    ("TR.F.DeferredTax",              "Deferred Tax",                     "#,##0"),
    ("TR.F.ChgWorkingCapital",        "Change in Working Capital",        "#,##0"),
    ("TR.F.OtherOperActivities",      "Other Operating Activities",       "#,##0"),
    ("TR.F.CashFromOperAct",          "Cash from Operations",             "#,##0"),
    # ── Investing
    ("TR.F.CapExp",                   "Capital Expenditures",             "#,##0"),
    ("TR.F.CashAcquisitions",         "Acquisitions",                     "#,##0"),
    ("TR.F.PurchaseInvestments",      "Purchase of Investments",          "#,##0"),
    ("TR.F.SaleInvestments",          "Sale / Maturity of Investments",   "#,##0"),
    ("TR.F.OtherInvestActiv",         "Other Investing Activities",       "#,##0"),
    ("TR.F.CashFromInvestAct",        "Cash from Investing",              "#,##0"),
    # ── Financing
    ("TR.F.IssuanceDebt",             "Issuance of Debt",                 "#,##0"),
    ("TR.F.RepaymentDebt",            "Repayment of Debt",                "#,##0"),
    ("TR.F.IssuanceCommonStock",      "Issuance of Common Stock",         "#,##0"),
    ("TR.F.RepurchCommonStock",       "Repurchase of Common Stock",       "#,##0"),
    ("TR.F.CashDividendsPaid",        "Dividends Paid",                   "#,##0"),
    ("TR.F.OtherFinancActiv",         "Other Financing Activities",       "#,##0"),
    ("TR.F.CashFromFinancAct",        "Cash from Financing",              "#,##0"),
    # ── Net & FCF
    ("TR.F.ForeignExchEffects",       "Foreign Exchange Effects",         "#,##0"),
    ("TR.F.NetChgCash",               "Net Change in Cash",               "#,##0"),
    ("TR.F.FreeCashFlow",             "Free Cash Flow",                   "#,##0"),
]

# Map sheet title → field list (used by get_all_statements and excel_writer)
STATEMENTS: dict[str, list] = {
    "Income Statement": INCOME_STATEMENT_FIELDS,
    "Balance Sheet":    BALANCE_SHEET_FIELDS,
    "Cash Flow":        CASH_FLOW_FIELDS,
}

# Summary fields for the country index sheet (latest values only)
SUMMARY_FIELDS = [
    "TR.CompanyName",
    "TR.Revenue",
    "TR.MarketCap",
    "TR.PEInclExtraTTM",
    "TR.EVToEBITDA",
    "TR.NetProfitMargin",
    "TR.ReturnOnEquity",
    "TR.TotalDebt",
    "TR.EBITDA",
]


# ── Eikon initialisation ───────────────────────────────────────────────────────

def init_eikon(app_key: str):
    ek.set_app_key(app_key)
    log.info("Eikon API key configured.")


# ── Retry wrapper ──────────────────────────────────────────────────────────────

def _call_with_retry(fn, *args, **kwargs):
    delay = RETRY_BACKOFF
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return fn(*args, **kwargs)
        except ek.EikonError as e:
            log.warning(f"Eikon error on attempt {attempt}/{MAX_RETRIES}: {e}")
            if attempt == MAX_RETRIES:
                raise
            log.info(f"Waiting {delay:.1f}s before retry…")
            time.sleep(delay)
            delay *= 2
        except Exception as e:
            log.warning(f"Unexpected error on attempt {attempt}/{MAX_RETRIES}: {e}")
            if attempt == MAX_RETRIES:
                raise
            time.sleep(delay)
            delay *= 2


# ── Company discovery ──────────────────────────────────────────────────────────

def get_companies_for_country(country_code: str) -> list[dict]:
    log.info(f"Fetching company list for country: {country_code}")
    screen_expr = (
        f'SCREEN(U(IN(Equity(active,public,primary))), '
        f'IN(TR.ExchangeCountryCode,"{country_code}"), '
        f'CURN=USD)'
    )
    df, err = _call_with_retry(ek.get_data, screen_expr, ["TR.RIC", "TR.CompanyName"])
    if err:
        log.warning(f"Partial error in screening for {country_code}: {err}")
    if df is None or df.empty:
        log.warning(f"No companies returned for {country_code}")
        return []
    df = df.dropna(subset=["RIC"])
    companies = [
        {"ric": row["RIC"], "name": row.get("Company Name", row["RIC"])}
        for _, row in df.iterrows()
    ]
    log.info(f"  → {len(companies)} companies found in {country_code}")
    return companies


# ── Single-statement fetch ─────────────────────────────────────────────────────

def _fetch_statement(ric: str, fields_def: list) -> pd.DataFrame:
    """
    Fetches one full standardised statement for a single RIC.

    fields_def is a list of (tr_field_code, label, excel_format) tuples.
    Returns a DataFrame shaped as:
        index   = line-item labels  (rows)
        columns = fiscal year strings e.g. "2015", "2016", …, "2024"
    Returns an empty DataFrame on failure.
    """
    field_codes = [f[0] for f in fields_def]
    labels      = [f[1] for f in fields_def]

    params = {"SDate": SDATE, "EDate": EDATE, "Frq": "FY", "ReportingState": STATEMENT_TYPE}

    df, err = _call_with_retry(ek.get_data, ric, field_codes, params)

    if err:
        log.debug(f"Partial error for {ric}: {err}")
    if df is None or df.empty:
        return pd.DataFrame()

    # Rename TR. codes → human labels
    code_to_label = {
        code.split(".")[-1]: label           # e.g. "TotRevenue" → "Total Revenue"
        for code, label in zip(field_codes, labels)
    }
    df = df.rename(columns=code_to_label)

    # Parse and extract fiscal year column
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df["Year"] = df["Date"].dt.year.astype(str)
    elif "Period End Date" in df.columns:
        df["Year"] = pd.to_datetime(df["Period End Date"], errors="coerce").dt.year.astype(str)
    else:
        # Fallback: keep as-is with integer index
        df["Year"] = df.index.astype(str)

    df = df.sort_values("Year")

    # Pivot: rows = line items, columns = years
    keep_labels = [l for l in labels if l in df.columns]
    years       = df["Year"].tolist()

    # Build transposed structure: label → {year: value}
    records = {}
    for label in keep_labels:
        row_vals = {}
        for _, data_row in df.iterrows():
            yr  = data_row["Year"]
            val = data_row.get(label)
            try:
                val = float(val)
            except (TypeError, ValueError):
                val = None
            row_vals[yr] = val
        records[label] = row_vals

    result = pd.DataFrame(records).T          # shape: (n_labels, n_years)
    result.index.name = "Line Item"

    # Preserve defined row order (some labels may be missing if Refinitiv omits them)
    ordered_index = [l for l in labels if l in result.index]
    result = result.reindex(ordered_index)

    return result


# ── All three statements ───────────────────────────────────────────────────────

def get_all_statements(ric: str) -> dict[str, pd.DataFrame]:
    """
    Fetches Income Statement, Balance Sheet, and Cash Flow Statement for a RIC.

    Returns:
      {
        "Income Statement": DataFrame,   # rows=line items, cols=years
        "Balance Sheet":    DataFrame,
        "Cash Flow":        DataFrame,
      }
    Each DataFrame may be empty if Refinitiv returns no data.
    """
    results = {}
    for sheet_name, fields_def in STATEMENTS.items():
        log.debug(f"  Fetching {sheet_name} for {ric}")
        try:
            df = _fetch_statement(ric, fields_def)
        except Exception as e:
            log.warning(f"  {sheet_name} failed for {ric}: {e}")
            df = pd.DataFrame()
        results[sheet_name] = df
        time.sleep(0.3)   # Small pause between the 3 statement calls per company
    return results


# ── Batched summary for country index ─────────────────────────────────────────

def get_summary_batch(rics: list[str]) -> pd.DataFrame:
    results = []
    for i in range(0, len(rics), BATCH_SIZE):
        batch = rics[i: i + BATCH_SIZE]
        log.debug(f"Summary batch {i // BATCH_SIZE + 1}: {len(batch)} RICs")
        try:
            df, _ = _call_with_retry(ek.get_data, batch, SUMMARY_FIELDS)
            if df is not None and not df.empty:
                results.append(df)
        except Exception as e:
            log.warning(f"Summary batch failed: {e}")
        time.sleep(DELAY_BETWEEN_BATCHES)
    return pd.concat(results, ignore_index=True) if results else pd.DataFrame()
