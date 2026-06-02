"""
excel_writer.py — Writes formatted Excel workbooks for each company.

Library choice: pandas + xlsxwriter (not openpyxl).
  - pandas writes each statement DataFrame to its sheet in a single vectorised
    call, avoiding per-cell Python loops over thousands of cells.
  - xlsxwriter streams directly to disk rather than building the full XML tree
    in memory, keeping RAM flat across 5,000+ companies.
  - openpyxl would be needed only if modifying existing files — this pipeline
    always creates fresh workbooks, so the write-only constraint is no constraint.

Each workbook has four sheets:
  1. Income Statement  — full standardised P&L
  2. Balance Sheet     — full standardised B/S
  3. Cash Flow         — full standardised cash flow statement
  4. Ratios            — 20 derived ratios as live cross-sheet Excel formulas

Colour coding (industry standard):
  Blue  (#0000FF) — raw data values from Refinitiv (inputs)
  Green (#008000) — cross-sheet formula references
"""

import os
import re
import pandas as pd

from utils.logger import get_logger

log = get_logger(__name__)

# ── Palette ────────────────────────────────────────────────────────────────────
CLR_HEADER_BG  = "#1F3864"
CLR_HEADER_FG  = "#FFFFFF"
CLR_SUBHDR_BG  = "#D6DCE4"
CLR_SECTION_BG = "#E9EFF7"
CLR_INPUT_FG   = "#0000FF"
CLR_LINK_FG    = "#008000"
CLR_ALT_ROW    = "#F5F5F5"
CLR_ACCENT     = "#2E75B6"
CLR_ROW_LBL_BG = "#EFEFEF"

SECTION_HEADERS = {
    "Total Revenue", "Cost of Revenue", "Operating Income (EBIT)",
    "Pre-Tax Income", "Net Income", "EPS (Basic)",
    "Total Current Assets", "Total Non-Current Assets", "Total Assets",
    "Total Current Liabilities", "Total Non-Current Liabilities",
    "Total Liabilities", "Total Equity", "Total Liabilities & Equity",
    "Cash from Operations", "Cash from Investing", "Cash from Financing",
    "Free Cash Flow",
}

RATIO_GROUPS = [
    ("PROFITABILITY",       None,  None),
    ("Gross Margin",        "=IFERROR({gp}/{rev},\"—\")",            "0.0%"),
    ("EBITDA Margin",       "=IFERROR({ebitda}/{rev},\"—\")",         "0.0%"),
    ("EBIT Margin",         "=IFERROR({ebit}/{rev},\"—\")",           "0.0%"),
    ("Net Profit Margin",   "=IFERROR({ni}/{rev},\"—\")",             "0.0%"),
    ("Return on Equity",    "=IFERROR({ni}/{eq},\"—\")",              "0.0%"),
    ("Return on Assets",    "=IFERROR({ni}/{assets},\"—\")",          "0.0%"),
    ("Return on Capital",   "=IFERROR({ebit}/({eq}+{debt}),\"—\")",  "0.0%"),
    ("LIQUIDITY",           None,  None),
    ("Current Ratio",       "=IFERROR({curr_a}/{curr_l},\"—\")",     "0.0x"),
    ("Quick Ratio",         "=IFERROR(({curr_a}-{inv})/{curr_l},\"—\")", "0.0x"),
    ("Cash Ratio",          "=IFERROR({cash}/{curr_l},\"—\")",       "0.0x"),
    ("LEVERAGE",            None,  None),
    ("Debt / Equity",       "=IFERROR({debt}/{eq},\"—\")",            "0.0x"),
    ("Net Debt / EBITDA",   "=IFERROR({net_debt}/{ebitda},\"—\")",   "0.0x"),
    ("Interest Coverage",   "=IFERROR({ebit}/ABS({int_exp}),\"—\")", "0.0x"),
    ("Debt / Total Assets", "=IFERROR({debt}/{assets},\"—\")",       "0.0%"),
    ("EFFICIENCY",          None,  None),
    ("Asset Turnover",      "=IFERROR({rev}/{assets},\"—\")",         "0.0x"),
    ("Receivables Turnover","=IFERROR({rev}/{recv},\"—\")",           "0.0x"),
    ("Inventory Turnover",  "=IFERROR({cogs}/{inv},\"—\")",           "0.0x"),
    ("CASH FLOW QUALITY",   None,  None),
    ("FCF Margin",          "=IFERROR({fcf}/{rev},\"—\")",            "0.0%"),
    ("FCF / Net Income",    "=IFERROR({fcf}/{ni},\"—\")",             "0.0x"),
    ("CapEx / Revenue",     "=IFERROR(ABS({capex})/{rev},\"—\")",    "0.0%"),
    ("Cash Conversion",     "=IFERROR({cfo}/{ebitda},\"—\")",        "0.0%"),
]


def _safe_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", name).strip()[:60]


def _col_letter(n: int) -> str:
    """1-based column index → Excel letter (1→A, 27→AA, …)."""
    result = ""
    while n:
        n, r = divmod(n - 1, 26)
        result = chr(65 + r) + result
    return result


# ── Format objects cache — created once per workbook ──────────────────────────

def _build_formats(wb):
    """
    Pre-create all xlsxwriter format objects once per workbook.
    xlsxwriter formats are attached to the workbook, not individual cells,
    so we build them once and reuse across all sheets.
    """
    base = {"font_name": "Arial", "font_size": 9, "border": 1,
            "border_color": "#CCCCCC"}

    def f(**kwargs):
        return wb.add_format({**base, **kwargs})

    return {
        # Headers
        "hdr":         wb.add_format({"font_name": "Arial", "font_size": 10,
                                       "bold": True, "font_color": CLR_HEADER_FG,
                                       "bg_color": CLR_HEADER_BG, "border": 1,
                                       "border_color": "#CCCCCC", "align": "center",
                                       "valign": "vcenter", "text_wrap": True}),
        "title":       wb.add_format({"font_name": "Arial", "font_size": 12,
                                       "bold": True, "font_color": CLR_ACCENT}),
        # Row labels
        "lbl":         f(bold=False, font_color="#000000", bg_color=CLR_ROW_LBL_BG, align="left"),
        "lbl_sect":    f(bold=True,  font_color="#000000", bg_color=CLR_SUBHDR_BG,
                         top=2, bottom=2, top_color="#888888", bottom_color="#888888",
                         align="left"),
        # Data cells — alternating rows
        "num_a":       f(num_format="#,##0",    font_color=CLR_INPUT_FG, bg_color=CLR_ALT_ROW),
        "num_w":       f(num_format="#,##0",    font_color=CLR_INPUT_FG, bg_color="#FFFFFF"),
        "num_s":       f(num_format="#,##0",    font_color=CLR_INPUT_FG, bg_color=CLR_SECTION_BG,
                         bold=True, top=2, bottom=2, top_color="#888888", bottom_color="#888888"),
        "pct_a":       f(num_format="0.0%",     font_color=CLR_INPUT_FG, bg_color=CLR_ALT_ROW),
        "pct_w":       f(num_format="0.0%",     font_color=CLR_INPUT_FG, bg_color="#FFFFFF"),
        "pct_s":       f(num_format="0.0%",     font_color=CLR_INPUT_FG, bg_color=CLR_SECTION_BG,
                         bold=True, top=2, bottom=2, top_color="#888888", bottom_color="#888888"),
        "eps_a":       f(num_format="#,##0.00", font_color=CLR_INPUT_FG, bg_color=CLR_ALT_ROW),
        "eps_w":       f(num_format="#,##0.00", font_color=CLR_INPUT_FG, bg_color="#FFFFFF"),
        # Ratio cells (green = cross-sheet link)
        "ratio_pct_a": f(num_format="0.0%",     font_color=CLR_LINK_FG, bg_color=CLR_ALT_ROW),
        "ratio_pct_w": f(num_format="0.0%",     font_color=CLR_LINK_FG, bg_color="#FFFFFF"),
        "ratio_mul_a": f(num_format='0.0"x"',   font_color=CLR_LINK_FG, bg_color=CLR_ALT_ROW),
        "ratio_mul_w": f(num_format='0.0"x"',   font_color=CLR_LINK_FG, bg_color="#FFFFFF"),
        "ratio_sect":  f(bold=True, font_color=CLR_HEADER_FG, bg_color=CLR_HEADER_BG,
                         top=2, bottom=2, top_color="#888888", bottom_color="#888888",
                         align="left"),
        # Index sheet
        "idx_hdr":     wb.add_format({"font_name": "Arial", "font_size": 10,
                                       "bold": True, "font_color": CLR_HEADER_FG,
                                       "bg_color": CLR_HEADER_BG, "border": 1,
                                       "border_color": "#CCCCCC", "align": "center"}),
        "idx_num_a":   f(num_format="#,##0",    bg_color=CLR_ALT_ROW, align="right"),
        "idx_num_w":   f(num_format="#,##0",    bg_color="#FFFFFF",    align="right"),
        "idx_txt_a":   f(bg_color=CLR_ALT_ROW, align="left"),
        "idx_txt_w":   f(bg_color="#FFFFFF",    align="left"),
    }


def _pick_data_fmt(fmts: dict, excel_fmt: str, is_section: bool, alt: bool):
    """Select the right pre-built format object for a data cell."""
    if is_section:
        return fmts["pct_s"] if excel_fmt == "0.0%" else fmts["num_s"]
    suffix = "_a" if alt else "_w"
    if excel_fmt == "0.0%":
        return fmts[f"pct{suffix}"]
    if excel_fmt in ("#,##0.00",):
        return fmts[f"eps{suffix}"]
    return fmts[f"num{suffix}"]


# ── Statement sheet ────────────────────────────────────────────────────────────

def _write_statement_sheet(
    wb, ws, sheet_title: str,
    df: pd.DataFrame, fields_def: list,
    company_name: str, ric: str,
    fmts: dict,
) -> tuple[list[str], dict[str, int]]:
    """
    Writes one financial statement sheet.

    Returns:
      years      — list of year strings e.g. ["2015", …, "2024"]
      label_rows — dict mapping line item label → Excel row index (0-based)
                   used by the Ratios sheet to build cross-sheet references
    """
    ws.hide_gridlines(2)
    ws.freeze_panes(2, 1)   # Freeze row 2 (headers) and column A (labels)
    ws.set_row(0, 22)
    ws.set_row(1, 18)

    # Title
    ws.write(0, 0, f"{company_name}  ({ric})  —  {sheet_title}  (USD, Annual)", fmts["title"])

    if df is None or df.empty:
        ws.write(2, 0, "No data returned from Refinitiv.")
        ws.set_column(0, 0, 45)
        return [], {}

    years   = [str(c) for c in df.columns]
    n_years = len(years)
    fmt_map = {label: fmt for _, label, fmt in fields_def}

    # Row 1: headers
    ws.write(1, 0, "Line Item", fmts["hdr"])
    for ci, yr in enumerate(years, start=1):
        ws.write(1, ci, yr, fmts["hdr"])

    # Data rows — bulk write via pandas then apply formatting column by column
    # pandas vectorised write for all data values
    label_rows: dict[str, int] = {}

    for ri, label in enumerate(df.index, start=2):
        is_section = label in SECTION_HEADERS
        alt        = ri % 2 == 0
        excel_fmt  = fmt_map.get(label, "#,##0")

        row_lbl_fmt = fmts["lbl_sect"] if is_section else fmts["lbl"]
        ws.write(ri, 0, label, row_lbl_fmt)
        label_rows[label] = ri   # Record for cross-sheet references

        data_fmt = _pick_data_fmt(fmts, excel_fmt, is_section, alt)
        for ci, yr in enumerate(years, start=1):
            val = df.loc[label, yr] if yr in df.columns else None
            val = None if (val is None or (isinstance(val, float) and pd.isna(val))) else val
            ws.write(ri, ci, val, data_fmt)

    # Column widths
    ws.set_column(0, 0, 36)
    ws.set_column(1, n_years, 14)

    return years, label_rows


# ── Ratios sheet ───────────────────────────────────────────────────────────────

def _write_ratios_sheet(
    wb, ws,
    years: list[str],
    company_name: str,
    ric: str,
    fmts: dict,
    row_index: dict[str, dict[str, int]],   # {sheet_name: {label: excel_row}}
):
    """
    Writes cross-sheet ratio formulas.

    row_index is built during statement writes and maps each label to its
    exact Excel row, so references like 'Income Statement'!D7 are always correct.
    """
    ws.hide_gridlines(2)
    ws.freeze_panes(2, 1)
    ws.set_row(0, 22)
    ws.set_row(1, 18)

    ws.write(0, 0, f"{company_name}  ({ric})  —  Financial Ratios", fmts["title"])

    if not years:
        ws.write(2, 0, "No statement data available to compute ratios.")
        ws.set_column(0, 0, 50)
        return

    ws.write(1, 0, "Ratio", fmts["hdr"])
    for ci, yr in enumerate(years, start=1):
        ws.write(1, ci, yr, fmts["hdr"])

    IS, BS, CF = "Income Statement", "Balance Sheet", "Cash Flow"

    def xref(sheet: str, label: str, col_idx: int) -> str:
        """
        Build a cross-sheet cell reference.
        col_idx is 1-based (col A of data = 1, first year = 2, …).
        row_index stores 0-based row numbers so we add 1 for Excel's 1-based rows.
        """
        r = row_index.get(sheet, {}).get(label)
        if r is None:
            return "0"
        col = _col_letter(col_idx + 1)   # +1: col A is labels, data starts at B
        safe = f"'{sheet}'" if " " in sheet else sheet
        return f"{safe}!{col}{r + 1}"    # +1: xlsxwriter rows are 0-based

    ri = 2
    for name, formula_tmpl, fmt in RATIO_GROUPS:
        is_section = formula_tmpl is None
        alt        = ri % 2 == 0

        if is_section:
            ws.write(ri, 0, name, fmts["ratio_sect"])
            for ci in range(1, len(years) + 1):
                ws.write(ri, ci, None, fmts["ratio_sect"])
        else:
            ws.write(ri, 0, name, fmts["lbl"])
            ratio_fmt_a = fmts["ratio_pct_a"] if fmt == "0.0%" else fmts["ratio_mul_a"]
            ratio_fmt_w = fmts["ratio_pct_w"] if fmt == "0.0%" else fmts["ratio_mul_w"]
            cell_fmt = ratio_fmt_a if alt else ratio_fmt_w

            for ci, _ in enumerate(years, start=1):
                formula = (formula_tmpl
                    .replace("{rev}",      xref(IS, "Total Revenue",              ci))
                    .replace("{gp}",       xref(IS, "Gross Profit",               ci))
                    .replace("{ebitda}",   xref(IS, "EBITDA",                     ci))
                    .replace("{ebit}",     xref(IS, "Operating Income (EBIT)",    ci))
                    .replace("{ni}",       xref(IS, "Net Income",                 ci))
                    .replace("{int_exp}",  xref(IS, "Interest Expense",           ci))
                    .replace("{cogs}",     xref(IS, "Cost of Revenue",            ci))
                    .replace("{assets}",   xref(BS, "Total Assets",               ci))
                    .replace("{eq}",       xref(BS, "Total Equity",               ci))
                    .replace("{debt}",     xref(BS, "Total Debt",                 ci))
                    .replace("{net_debt}", xref(BS, "Net Debt",                   ci))
                    .replace("{curr_a}",   xref(BS, "Total Current Assets",       ci))
                    .replace("{curr_l}",   xref(BS, "Total Current Liabilities",  ci))
                    .replace("{cash}",     xref(BS, "Total Cash & ST Investments",ci))
                    .replace("{recv}",     xref(BS, "Net Receivables",            ci))
                    .replace("{inv}",      xref(BS, "Inventories",                ci))
                    .replace("{fcf}",      xref(CF, "Free Cash Flow",             ci))
                    .replace("{cfo}",      xref(CF, "Cash from Operations",       ci))
                    .replace("{capex}",    xref(CF, "Capital Expenditures",       ci))
                )
                ws.write_formula(ri, ci, formula, cell_fmt)

        ri += 1

    ws.set_column(0, 0, 28)
    ws.set_column(1, len(years), 14)


# ── Per-company workbook ───────────────────────────────────────────────────────

def write_company_workbook(
    ric: str,
    company_name: str,
    statements: dict[str, pd.DataFrame],
    fields_defs: dict[str, list],
    country_folder: str,
) -> str:
    safe_name   = _safe_filename(company_name)
    company_dir = os.path.join(country_folder, safe_name)
    os.makedirs(company_dir, exist_ok=True)
    filepath = os.path.join(company_dir, f"{safe_name}.xlsx")

    writer = pd.ExcelWriter(filepath, engine="xlsxwriter")
    wb     = writer.book

    fmts       = _build_formats(wb)
    all_years  = []
    row_index  = {}   # {sheet_title: {label: row_idx}}

    for sheet_title, fields_def in fields_defs.items():
        df = statements.get(sheet_title, pd.DataFrame())
        ws = wb.add_worksheet(sheet_title)
        years, label_rows = _write_statement_sheet(
            wb, ws, sheet_title, df, fields_def, company_name, ric, fmts
        )
        row_index[sheet_title] = label_rows
        if years and not all_years:
            all_years = years

    ws_ratios = wb.add_worksheet("Ratios")
    _write_ratios_sheet(wb, ws_ratios, all_years, company_name, ric, fmts, row_index)

    writer.close()
    log.debug(f"Written: {filepath}")
    return filepath


# ── Country index workbook ─────────────────────────────────────────────────────

def write_country_index(country_name: str, country_folder: str,
                        summary_df: pd.DataFrame):
    filepath = os.path.join(country_folder, "_Index.xlsx")

    writer = pd.ExcelWriter(filepath, engine="xlsxwriter")
    wb     = writer.book
    fmts   = _build_formats(wb)
    ws     = wb.add_worksheet("Index")

    ws.hide_gridlines(2)
    ws.freeze_panes(2, 0)
    ws.set_row(0, 24)
    ws.set_row(1, 20)

    ws.write(0, 0,
             f"{country_name} — Listed Companies Index",
             wb.add_format({"font_name": "Arial", "font_size": 13,
                             "bold": True, "font_color": CLR_ACCENT}))

    if summary_df.empty:
        ws.write(2, 0, "No summary data available.")
        writer.close()
        return

    for ci, col in enumerate(summary_df.columns):
        ws.write(1, ci, col, fmts["idx_hdr"])

    for ri, (_, row) in enumerate(summary_df.iterrows(), start=2):
        alt = ri % 2 == 0
        for ci, val in enumerate(row.values):
            is_num = isinstance(val, (int, float)) and not pd.isna(val)
            if is_num:
                fmt = fmts["idx_num_a"] if alt else fmts["idx_num_w"]
            else:
                fmt = fmts["idx_txt_a"] if alt else fmts["idx_txt_w"]
                val = str(val) if val is not None and not (isinstance(val, float) and pd.isna(val)) else ""
            ws.write(ri, ci, val, fmt)

    # Auto-fit column widths based on header length
    for ci, col in enumerate(summary_df.columns):
        max_len = max(len(str(col)),
                      summary_df.iloc[:, ci].astype(str).str.len().max())
        ws.set_column(ci, ci, min(int(max_len) + 4, 30))

    writer.close()
    log.info(f"Country index written: {filepath}")
