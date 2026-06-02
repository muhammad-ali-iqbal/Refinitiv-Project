"""
excel_writer.py — Writes formatted Excel workbooks for each company.

Each workbook has five sheets:
  1. "Income Statement" — full standardised P&L, rows=line items, cols=years
  2. "Balance Sheet"    — full standardised B/S
  3. "Cash Flow"        — full standardised cash flow statement
  4. "Ratios"           — derived ratios via Excel formulas cross-referencing sheets 1-3
  5. (country-level)    "_Index.xlsx" — one row per company, latest snapshot

Colour coding follows industry standard:
  Blue  (#0000FF) — raw data values (inputs from Refinitiv)
  Black (#000000) — formula-calculated cells
  Green (#008000) — cross-sheet formula references
"""

import os
import re
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from utils.logger import get_logger

log = get_logger(__name__)

# ── Palette ────────────────────────────────────────────────────────────────────
CLR_HEADER_BG  = "1F3864"
CLR_HEADER_FG  = "FFFFFF"
CLR_SUBHDR_BG  = "D6DCE4"
CLR_SECTION_BG = "E9EFF7"   # Lighter blue — section group headers within a sheet
CLR_INPUT_FG   = "0000FF"
CLR_FORMULA_FG = "000000"
CLR_LINK_FG    = "008000"
CLR_ALT_ROW    = "F5F5F5"
CLR_ACCENT     = "2E75B6"

THIN   = Side(style="thin",   color="CCCCCC")
MEDIUM = Side(style="medium", color="888888")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
BORDER_SECTION = Border(left=THIN, right=THIN, top=MEDIUM, bottom=MEDIUM)


# ── Section groupings — which line items open a visual section header ──────────
# These labels get a slightly darker background to break up the statement visually.
SECTION_HEADERS = {
    # Income Statement
    "Total Revenue", "Cost of Revenue", "Operating Income (EBIT)",
    "Pre-Tax Income", "Net Income", "EPS (Basic)",
    # Balance Sheet
    "Total Current Assets", "Total Non-Current Assets", "Total Assets",
    "Total Current Liabilities", "Total Non-Current Liabilities",
    "Total Liabilities", "Total Equity", "Total Liabilities & Equity",
    # Cash Flow
    "Cash from Operations", "Cash from Investing", "Cash from Financing",
    "Free Cash Flow",
}


def _safe_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", name).strip()[:60]


def _apply_header(ws, row: int, col: int, value, span: int = 1):
    cell = ws.cell(row=row, column=col, value=value)
    cell.font      = Font(name="Arial", bold=True, color=CLR_HEADER_FG, size=10)
    cell.fill      = PatternFill("solid", fgColor=CLR_HEADER_BG)
    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    cell.border    = BORDER
    if span > 1:
        ws.merge_cells(start_row=row, start_column=col,
                       end_row=row, end_column=col + span - 1)


def _fmt_cell(cell, number_format: str, color: str = CLR_INPUT_FG,
              bold: bool = False, bg: str | None = None):
    cell.font          = Font(name="Arial", color=color, size=9, bold=bold)
    cell.number_format = number_format
    cell.alignment     = Alignment(horizontal="right")
    cell.border        = BORDER
    if bg:
        cell.fill = PatternFill("solid", fgColor=bg)


def _write_statement_sheet(wb: Workbook, sheet_title: str,
                            df: pd.DataFrame, fields_def: list,
                            company_name: str, ric: str) -> list[str]:
    """
    Writes one financial statement sheet to wb.

    df      — DataFrame with index=line item labels, columns=year strings
    fields_def — list of (code, label, excel_format) from fetcher.STATEMENTS

    Returns the list of year column strings (used by the Ratios sheet).
    """
    ws = wb.create_sheet(sheet_title)
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "B3"

    # Title
    tc = ws.cell(row=1, column=1,
                 value=f"{company_name}  ({ric})  —  {sheet_title}  (USD, Annual)")
    tc.font      = Font(name="Arial", bold=True, size=12, color=CLR_ACCENT)
    tc.alignment = Alignment(horizontal="left")
    ws.row_dimensions[1].height = 22

    if df is None or df.empty:
        ws.cell(row=3, column=1, value="No data returned from Refinitiv.")
        ws.column_dimensions["A"].width = 45
        return []

    years   = [str(c) for c in df.columns]
    n_years = len(years)

    # Row 2: column headers
    lbl_cell = ws.cell(row=2, column=1, value="Line Item")
    lbl_cell.font      = Font(name="Arial", bold=True, size=9, color=CLR_HEADER_FG)
    lbl_cell.fill      = PatternFill("solid", fgColor=CLR_HEADER_BG)
    lbl_cell.border    = BORDER
    lbl_cell.alignment = Alignment(horizontal="left")

    for ci, yr in enumerate(years, start=2):
        _apply_header(ws, row=2, col=ci, value=yr)
    ws.row_dimensions[2].height = 18

    # Build format lookup
    fmt_map = {label: fmt for _, label, fmt in fields_def}

    # Data rows
    for ri, label in enumerate(df.index, start=3):
        is_section = label in SECTION_HEADERS
        row_bg     = CLR_SECTION_BG if is_section else (CLR_ALT_ROW if ri % 2 == 0 else "FFFFFF")
        border     = BORDER_SECTION if is_section else BORDER

        lc = ws.cell(row=ri, column=1, value=label)
        lc.font      = Font(name="Arial", bold=is_section, size=9)
        lc.fill      = PatternFill("solid", fgColor=CLR_SUBHDR_BG if is_section else "EFEFEF")
        lc.border    = border
        lc.alignment = Alignment(horizontal="left")

        fmt = fmt_map.get(label, "#,##0")

        for ci, yr in enumerate(years, start=2):
            val = df.loc[label, yr] if yr in df.columns else None
            if pd.isna(val):
                val = None
            cell = ws.cell(row=ri, column=ci, value=val)
            cell.fill = PatternFill("solid", fgColor=row_bg)
            cell.border = border
            _fmt_cell(cell, fmt, color=CLR_INPUT_FG, bold=is_section)

    ws.column_dimensions["A"].width = 36
    for ci in range(2, n_years + 2):
        ws.column_dimensions[get_column_letter(ci)].width = 14

    return years


def _write_ratios_sheet(wb: Workbook, years: list[str],
                        company_name: str, ric: str):
    """
    Writes the Ratios sheet using Excel formulas that cross-reference
    the Income Statement, Balance Sheet, and Cash Flow sheets.
    All formulas use IFERROR to suppress divide-by-zero and missing data.
    """
    ws = wb.create_sheet("Ratios")
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "B3"

    tc = ws.cell(row=1, column=1,
                 value=f"{company_name}  ({ric})  —  Financial Ratios")
    tc.font      = Font(name="Arial", bold=True, size=12, color=CLR_ACCENT)
    tc.alignment = Alignment(horizontal="left")
    ws.row_dimensions[1].height = 22

    if not years:
        ws.cell(row=3, column=1, value="No statement data available to compute ratios.")
        ws.column_dimensions["A"].width = 50
        return

    lbl_cell = ws.cell(row=2, column=1, value="Ratio")
    lbl_cell.font      = Font(name="Arial", bold=True, size=9, color=CLR_HEADER_FG)
    lbl_cell.fill      = PatternFill("solid", fgColor=CLR_HEADER_BG)
    lbl_cell.border    = BORDER
    lbl_cell.alignment = Alignment(horizontal="left")
    for ci, yr in enumerate(years, start=2):
        _apply_header(ws, row=2, col=ci, value=yr)

    # ── Helper: find the Excel row of a label in a given sheet ────────────────
    # Row 1 = title, Row 2 = headers, data starts at Row 3.
    # We need the row index of each label within its respective sheet.
    def _sheet_row(sheet_name: str, label: str) -> int | None:
        if sheet_name not in wb.sheetnames:
            return None
        ws_ref = wb[sheet_name]
        for row in ws_ref.iter_rows(min_row=3):
            cell = row[0]
            if cell.value == label:
                return cell.row
        return None

    def xref(sheet: str, label: str, col_idx: int) -> str:
        """Returns a cross-sheet cell reference, e.g. 'Income Statement'!D7"""
        r = _sheet_row(sheet, label)
        if r is None:
            return "0"
        col = get_column_letter(col_idx)
        # Sheet names with spaces must be quoted
        safe_sheet = f"'{sheet}'" if " " in sheet else sheet
        return f"{safe_sheet}!{col}{r}"

    IS = "Income Statement"
    BS = "Balance Sheet"
    CF = "Cash Flow"

    # ── Ratio groups ──────────────────────────────────────────────────────────
    # Format: (section_label, None) = section header row (no formula)
    #         (ratio_name, formula_template, excel_format)
    RATIO_GROUPS = [
        # ── Profitability
        ("PROFITABILITY", None, None),
        ("Gross Margin",         "=IFERROR({gp}/{rev},\"—\")",           "0.0%"),
        ("EBITDA Margin",        "=IFERROR({ebitda}/{rev},\"—\")",        "0.0%"),
        ("EBIT Margin",          "=IFERROR({ebit}/{rev},\"—\")",          "0.0%"),
        ("Net Profit Margin",    "=IFERROR({ni}/{rev},\"—\")",            "0.0%"),
        ("Return on Equity",     "=IFERROR({ni}/{eq},\"—\")",             "0.0%"),
        ("Return on Assets",     "=IFERROR({ni}/{assets},\"—\")",         "0.0%"),
        ("Return on Capital",    "=IFERROR({ebit}/({eq}+{debt}),\"—\")", "0.0%"),
        # ── Liquidity
        ("LIQUIDITY", None, None),
        ("Current Ratio",        "=IFERROR({curr_a}/{curr_l},\"—\")",    "0.0x"),
        ("Quick Ratio",          "=IFERROR(({curr_a}-{inv})/{curr_l},\"—\")", "0.0x"),
        ("Cash Ratio",           "=IFERROR({cash}/{curr_l},\"—\")",      "0.0x"),
        # ── Leverage
        ("LEVERAGE", None, None),
        ("Debt / Equity",        "=IFERROR({debt}/{eq},\"—\")",           "0.0x"),
        ("Net Debt / EBITDA",    "=IFERROR({net_debt}/{ebitda},\"—\")",  "0.0x"),
        ("Interest Coverage",    "=IFERROR({ebit}/ABS({int_exp}),\"—\")", "0.0x"),
        ("Debt / Total Assets",  "=IFERROR({debt}/{assets},\"—\")",      "0.0%"),
        # ── Efficiency
        ("EFFICIENCY", None, None),
        ("Asset Turnover",       "=IFERROR({rev}/{assets},\"—\")",        "0.0x"),
        ("Receivables Turnover", "=IFERROR({rev}/{recv},\"—\")",          "0.0x"),
        ("Inventory Turnover",   "=IFERROR({cogs}/{inv},\"—\")",          "0.0x"),
        # ── Cash Flow Quality
        ("CASH FLOW QUALITY", None, None),
        ("FCF Margin",           "=IFERROR({fcf}/{rev},\"—\")",           "0.0%"),
        ("FCF / Net Income",     "=IFERROR({fcf}/{ni},\"—\")",            "0.0x"),
        ("CapEx / Revenue",      "=IFERROR(ABS({capex})/{rev},\"—\")",   "0.0%"),
        ("Cash Conversion",      "=IFERROR({cfo}/{ebitda},\"—\")",       "0.0%"),
    ]

    ri = 3
    for group_item in RATIO_GROUPS:
        name, formula_tmpl, fmt = group_item
        row_color = CLR_ALT_ROW if ri % 2 == 0 else "FFFFFF"
        is_section = formula_tmpl is None

        lc = ws.cell(row=ri, column=1, value=name)
        lc.font      = Font(name="Arial", bold=True, size=9,
                            color=CLR_HEADER_FG if is_section else "000000")
        lc.fill      = PatternFill("solid", fgColor=CLR_HEADER_BG if is_section else CLR_SUBHDR_BG)
        lc.border    = BORDER_SECTION if is_section else BORDER
        lc.alignment = Alignment(horizontal="left")

        if is_section:
            # Merge across all year columns for the section header
            for ci in range(2, len(years) + 2):
                cell = ws.cell(row=ri, column=ci)
                cell.fill   = PatternFill("solid", fgColor=CLR_HEADER_BG)
                cell.border = BORDER_SECTION
        else:
            for ci, _ in enumerate(years, start=2):
                formula = (formula_tmpl
                    .replace("{rev}",     xref(IS, "Total Revenue",              ci))
                    .replace("{gp}",      xref(IS, "Gross Profit",               ci))
                    .replace("{ebitda}",  xref(IS, "EBITDA",                     ci))
                    .replace("{ebit}",    xref(IS, "Operating Income (EBIT)",    ci))
                    .replace("{ni}",      xref(IS, "Net Income",                 ci))
                    .replace("{int_exp}", xref(IS, "Interest Expense",           ci))
                    .replace("{cogs}",    xref(IS, "Cost of Revenue",            ci))
                    .replace("{assets}",  xref(BS, "Total Assets",               ci))
                    .replace("{eq}",      xref(BS, "Total Equity",               ci))
                    .replace("{debt}",    xref(BS, "Total Debt",                 ci))
                    .replace("{net_debt}",xref(BS, "Net Debt",                   ci))
                    .replace("{curr_a}",  xref(BS, "Total Current Assets",       ci))
                    .replace("{curr_l}",  xref(BS, "Total Current Liabilities",  ci))
                    .replace("{cash}",    xref(BS, "Total Cash & ST Investments",ci))
                    .replace("{recv}",    xref(BS, "Net Receivables",            ci))
                    .replace("{inv}",     xref(BS, "Inventories",                ci))
                    .replace("{fcf}",     xref(CF, "Free Cash Flow",             ci))
                    .replace("{cfo}",     xref(CF, "Cash from Operations",       ci))
                    .replace("{capex}",   xref(CF, "Capital Expenditures",       ci))
                )
                cell = ws.cell(row=ri, column=ci, value=formula)
                cell.fill = PatternFill("solid", fgColor=row_color)
                _fmt_cell(cell, fmt, color=CLR_LINK_FG)

        ri += 1

    ws.column_dimensions["A"].width = 28
    for ci in range(2, len(years) + 2):
        ws.column_dimensions[get_column_letter(ci)].width = 14


# ── Per-company workbook ───────────────────────────────────────────────────────

def write_company_workbook(
    ric: str,
    company_name: str,
    statements: dict[str, pd.DataFrame],
    fields_defs: dict[str, list],
    country_folder: str,
) -> str:
    """
    Creates Data/Country/CompanyName/CompanyName.xlsx with sheets:
      Income Statement | Balance Sheet | Cash Flow | Ratios

    statements  — {"Income Statement": df, "Balance Sheet": df, "Cash Flow": df}
    fields_defs — from fetcher.STATEMENTS (needed for format strings)
    """
    safe_name   = _safe_filename(company_name)
    company_dir = os.path.join(country_folder, safe_name)
    os.makedirs(company_dir, exist_ok=True)
    filepath = os.path.join(company_dir, f"{safe_name}.xlsx")

    wb = Workbook()
    wb.remove(wb.active)   # Remove default blank sheet

    all_years = []

    for sheet_title, fields_def in fields_defs.items():
        df = statements.get(sheet_title, pd.DataFrame())
        years = _write_statement_sheet(wb, sheet_title, df, fields_def,
                                       company_name, ric)
        if years and not all_years:
            all_years = years   # Use year list from first non-empty statement

    _write_ratios_sheet(wb, all_years, company_name, ric)

    wb.save(filepath)
    log.debug(f"Written: {filepath}")
    return filepath


# ── Country index workbook ─────────────────────────────────────────────────────

def write_country_index(country_name: str, country_folder: str,
                        summary_df: pd.DataFrame):
    filepath = os.path.join(country_folder, "_Index.xlsx")
    wb = Workbook()
    ws = wb.active
    ws.title = "Index"
    ws.sheet_view.showGridLines = False
    ws.freeze_panes = "A3"

    tc = ws.cell(row=1, column=1, value=f"{country_name} — Listed Companies Index")
    tc.font      = Font(name="Arial", bold=True, size=13, color=CLR_ACCENT)
    tc.alignment = Alignment(horizontal="left")
    ws.row_dimensions[1].height = 24

    if summary_df.empty:
        ws.cell(row=3, column=1, value="No summary data available.")
        wb.save(filepath)
        return

    for ci, h in enumerate(summary_df.columns, start=1):
        _apply_header(ws, row=2, col=ci, value=h)
    ws.row_dimensions[2].height = 20

    for ri, (_, row) in enumerate(summary_df.iterrows(), start=3):
        row_color = CLR_ALT_ROW if ri % 2 == 0 else "FFFFFF"
        for ci, val in enumerate(row.values, start=1):
            cell = ws.cell(row=ri, column=ci, value=val)
            cell.fill      = PatternFill("solid", fgColor=row_color)
            cell.font      = Font(name="Arial", size=9)
            cell.border    = BORDER
            cell.alignment = Alignment(
                horizontal="right" if isinstance(val, (int, float)) else "left"
            )

    for col in ws.columns:
        max_len = max((len(str(cell.value or "")) for cell in col), default=10)
        ws.column_dimensions[col[0].column_letter].width = min(max_len + 4, 30)

    wb.save(filepath)
    log.info(f"Country index written: {filepath}")
