# pipeline/

The three core modules. Each has a single responsibility.

---

## fetcher.py

All Eikon API communication. Nothing outside this file imports `eikon` directly.

### Statement field definitions

Three module-level lists define every line item fetched per statement:

| List | Items | Sheet |
|---|---|---|
| `INCOME_STATEMENT_FIELDS` | 26 | Revenue → EPS, D&A, tax |
| `BALANCE_SHEET_FIELDS` | 31 | Current/non-current assets, liabilities, equity |
| `CASH_FLOW_FIELDS` | 22 | Operating, investing, financing, FCF |

All use Refinitiv's `TR.F.*` standardised namespace. Each entry is a tuple:
```python
("TR.F.TotRevenue", "Total Revenue", "#,##0")
#   field code        display label    Excel format
```

The `STATEMENTS` dict combines all three and is imported by the orchestrator and excel_writer:
```python
STATEMENTS = {
    "Income Statement": INCOME_STATEMENT_FIELDS,
    "Balance Sheet":    BALANCE_SHEET_FIELDS,
    "Cash Flow":        CASH_FLOW_FIELDS,
}
```

### Key functions

**`init_eikon(app_key)`** — Configures the Eikon proxy. Call once at startup.

**`get_companies_for_country(country_code) → list[dict]`** — Screens all active primary-listed equities in a country. Returns `[{"ric": ..., "name": ...}, ...]`.

**`_fetch_statement(ric, fields_def) → pd.DataFrame`** — Fetches one statement for one RIC. Returns a DataFrame with index = line item labels, columns = fiscal year strings (`"2015"`, `"2016"`, …). Private — called by `get_all_statements`.

**`get_all_statements(ric) → dict[str, pd.DataFrame]`** — Calls `_fetch_statement` three times (once per statement) with a 0.3s pause between each, and returns all three DataFrames keyed by sheet name.

**`get_summary_batch(rics) → pd.DataFrame`** — Fetches a one-row latest-value snapshot for a list of RICs. Used for the country `_Index.xlsx`.

### Rate limit strategy

All external calls go through `_call_with_retry()` — exponential back-off on `EikonError`, up to `MAX_RETRIES` attempts. Each company now makes **3 API calls** (one per statement), so `DELAY_BETWEEN_COMPANIES` defaults to 0.5s.

---

## excel_writer.py

All Excel formatting and file creation. No Eikon imports.

### Library choice: pandas + xlsxwriter (not openpyxl)

This pipeline uses `pandas` + `xlsxwriter` instead of `openpyxl` for two reasons specific to this use case:

**Performance at scale.** openpyxl builds the entire XML workbook tree in memory, writing cell by cell through Python objects. At 5,000+ companies × 3 statements × ~25 line items × 10 years, that's ~750 cell-write operations per company through slow Python loops. xlsxwriter streams directly to disk, keeping memory flat regardless of workbook size and running 3–5× faster on bulk writes.

**Data flow efficiency.** Refinitiv data comes back as pandas DataFrames. Writing a DataFrame through openpyxl means unpacking it back into Python objects row by row. pandas + xlsxwriter keeps the data in its efficient columnar form all the way to the file.

**The one trade-off:** xlsxwriter is write-only — you cannot read back or modify an existing file. This is not a constraint here because the pipeline always creates fresh workbooks. If a future requirement arises to update existing files in-place, openpyxl would be needed for that operation specifically.

### Workbook structure

Each company workbook has four sheets written in this order:

1. **Income Statement** — `_write_statement_sheet()`
2. **Balance Sheet** — `_write_statement_sheet()`
3. **Cash Flow** — `_write_statement_sheet()`
4. **Ratios** — `_write_ratios_sheet()`

The Ratios sheet is written last. As each statement sheet is written, `_write_statement_sheet()` returns a `label_rows` dict mapping every line item label to its Excel row index. These are collected into `row_index` and passed to `_write_ratios_sheet()`, which uses them to build exact cross-sheet references like `'Income Statement'!D7` without any read-back from already-written sheets.

### Format objects

All xlsxwriter format objects are created once per workbook via `_build_formats(wb)` and reused across all sheets. xlsxwriter formats are workbook-scoped — creating them per-cell would be both slower and incorrect.

### Visual structure of each statement sheet

```
Row 1:  Title bar (company name, RIC, statement name)
Row 2:  Column headers  [Line Item | 2015 | 2016 | … | 2024]
Row 3+: Data rows — one per line item
        Section totals (e.g. Total Revenue, Total Assets) get a
        slightly darker background and medium border to visually
        break the statement into logical groups.
```

### Ratios sheet

20 ratios across 5 groups (Profitability, Liquidity, Leverage, Efficiency, Cash Flow Quality). Each cell contains a live Excel formula:
```
=IFERROR('Income Statement'!D7/'Balance Sheet'!D21,"—")
```
`IFERROR` suppresses divide-by-zero and missing data gracefully. Green font (`#008000`) follows industry convention for cross-sheet references.

### Colour palette

| Constant | Hex | Used for |
|---|---|---|
| `CLR_HEADER_BG` | `#1F3864` | Column/section headers |
| `CLR_SECTION_BG` | `#E9EFF7` | Section total rows within statements |
| `CLR_SUBHDR_BG` | `#D6DCE4` | Row label background |
| `CLR_INPUT_FG` | `#0000FF` | Raw data values (blue = inputs) |
| `CLR_LINK_FG` | `#008000` | Cross-sheet formula references (green) |

---

## orchestrator.py

Drives the full pipeline loop. Imports from `fetcher`, `excel_writer`, and both utilities.

### Per-company execution

```
if is_done(country_code, ric):  → skip
statements = get_all_statements(ric)
write_company_workbook(ric, name, statements, STATEMENTS, country_folder)
mark_done(country_code, ric)
```

`STATEMENTS` (the field definition dict) is passed through to `write_company_workbook` so the writer has access to Excel format strings without importing from fetcher directly.

### Entry point

```python
from pipeline.orchestrator import run
run(app_key="YOUR_KEY")

# Restrict to subset:
run(app_key="YOUR_KEY", countries={"Japan": "JPN", "Australia": "AUS"})
```
