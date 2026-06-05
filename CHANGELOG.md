# Changelog

## 2026-06-04 — Migration to lseg-data + API compatibility fixes

### Context
First run session with the IBA Refinitiv API key. The original codebase was written
for the deprecated `eikon` package and the `TR.F.*` standardised field namespace.
Multiple breaking changes were discovered and fixed through iterative debugging.

---

### 1. Package: `eikon` → `lseg-data`

**File:** `pipeline/fetcher.py`

The project already referenced `lseg-data` in comments but had not been fully migrated.

| Old | New |
|-----|-----|
| `from lseg.data.errors import LsegDataError` | `from lseg.data.errors import LDError` |
| `df, err = ld.get_data(...)` | `df = ld.get_data(...)` — returns single DataFrame, not tuple |
| `Period="FY"` parameter | Removed — unrecognised in this API version |
| `ReportingType="STD"` parameter | Removed — unrecognised in this API version |

`ld.get_data()` in the installed version returns a `DataFrame` directly (not a
`(DataFrame, errors)` tuple as the old `eikon.get_data()` did).

---

### 2. Country codes: ISO-3 → ISO-2

**File:** `config/settings.py`

`TR.ExchangeCountryCode` uses 2-letter ISO codes. The original `COUNTRIES` dict
used 3-letter codes (e.g. `"USA"`) which matched zero rows in every SCREEN query.

```python
# Before (returned 0 companies)
"United States": "USA"

# After (returns ~13,953 companies)
"United States": "US"
```

Full mapping updated for all 10 countries (US, GB, DE, FR, JP, CN, IN, BR, AU, CA).

---

### 3. Field namespace: `TR.F.*` → `TR.*`

**File:** `pipeline/fetcher.py` — `INCOME_STATEMENT_FIELDS`, `BALANCE_SHEET_FIELDS`, `CASH_FLOW_FIELDS`

The IBA API key does **not** include the Refinitiv Fundamentals subscription required
for the `TR.F.*` standardised namespace. Only 3 of 55 `TR.F.*` fields resolved
(`TR.F.TotRevenue`, `TR.F.EBITDA`, `TR.F.TotAssets`). All others returned
`"Unable to resolve all requested fields"`.

Switched to the `TR.*` namespace which works with the available subscription:

| Statement | Fields available |
|-----------|-----------------|
| Income Statement | Revenue, Gross Profit, EBIT, EBITDA, Net Income, D&A, Interest Expense |
| Balance Sheet | Cash & ST Investments, Current Assets, Total Assets, Current Liabilities, LT Debt, Total Debt, Total Liabilities, Total Equity, Retained Earnings, Book Value/Share |
| Cash Flow | Free Cash Flow, Net Change in Cash |

**Note:** Cash Flow is limited to 2 fields under the current subscription. If a
higher-tier key is obtained later, restore the full `TR.F.*` field lists from git
history and remove this constraint.

---

### 4. Date extraction: `.date` sub-field → `TR.F.PeriodEndDate`

**File:** `pipeline/fetcher.py` — `_fetch_statement()`

The old code passed a SCREEN expression as the universe to get multiple companies
in one call. That no longer works — `ld.get_data()` must be called per-RIC.

New data shape: the API returns **one row per fiscal year** (long format) rather
than one column per fiscal year. `_fetch_statement` now:

1. Appends `TR.F.PeriodEndDate` to the field list to get fiscal year end dates
   (this field is compatible with `TR.*` value fields in the same request)
2. Renames columns positionally (API display names are not stable across versions)
3. Pivots to wide format: index = line item labels, columns = `YYYY-MM-DD` dates

```
# API response (long)               # Output DataFrame (wide)
Instrument | Revenue | Period End    Index          | 2023-09-30 | 2024-09-28
AAPL.O     | 383285  | 2023-09-30    Total Revenue  | 383285     | 391035
AAPL.O     | 391035  | 2024-09-28    Gross Profit   | 169148     | 180683
```

Note: `TR.F.PeriodEndDate` with the `.date` sub-field approach (e.g.
`TR.Revenue.date`) suppresses all other fields when mixed — use `TR.F.PeriodEndDate`
as a standalone field in the request instead.

---

### 5. Ratios sheet: per-formula dependency checking

**File:** `pipeline/excel_writer.py` — `_write_ratios_sheet()`

The old code checked `if all(rows are not None)` — meaning if any single
referenced label was missing (e.g. "Cost of Revenue" or "Capital Expenditures"
which are not in the current field set), the entire Ratios sheet was left blank.

Changed to per-formula dependency checking: each ratio only requires its own
referenced rows to be present. Available ratios (given current fields):

- **EBITDA Margin %** ✓ (Revenue + EBITDA)
- **Net Margin %** ✓ (Revenue + Net Income)
- **Debt / Equity** ✓ (Total Debt + Total Equity)
- **Net Debt / EBITDA** ✓ (Total Debt + Cash + EBITDA)
- **Asset Turnover** ✓ (Revenue + Total Assets)
- **FCF Conversion** ✓ (Free Cash Flow + Net Income)
- **FCF Margin %** ✓ (Free Cash Flow + Revenue)
- **Gross Margin %** — shows `N/A` (needs "Cost of Revenue", not in current fields)
- **CapEx / Revenue** — shows `N/A` (needs "Capital Expenditures", not in current fields)

---

### 6. Excel writer: `<NA>` → `None`

**File:** `pipeline/excel_writer.py` — `_write_statement_sheet()`

pandas `<NA>` (used for integer NA) cannot be written to Excel cells by openpyxl.
Added `val = None if pd.isna(val) else val` before each cell write.

---

### 7. Run_pipeline.py: guard check updated

**File:** `run_pipeline.py`

The hardcoded guard check compared against the old placeholder key. Updated to:
```python
if not LSEG_APP_KEY:   # was: if LSEG_APP_KEY == "<old placeholder>"
```

---

### 8. Test limit active — REMOVE BEFORE FULL RUN

**File:** `pipeline/orchestrator.py` line ~58

```python
companies = companies[:5]   # TEST LIMIT — remove this line for a full run
```

This caps each country at 5 companies for testing. **Remove before the real run.**

---

### Current state

- Pipeline runs end-to-end and produces valid `.xlsx` files
- Tested on `AAPL.O` — 7 income / 10 balance / 2 cash flow fields, 10 years
- Output path: `C:\Users\Financefaculty\Desktop\Data\`
- API key in `run_pipeline.py`: IBA key, expires 2026-06-03
- Only `"United States": "US"` is active in `config/settings.py` (others commented out)

### Next session checklist

- [ ] Open the `test_AAPL.xlsx` on Desktop and verify data looks correct
- [ ] Remove `companies = companies[:5]` from `orchestrator.py` for full run
- [ ] Uncomment additional countries in `config/settings.py` if desired
- [ ] Run `python run_pipeline.py` — expect ~14,000 US companies, 12–16 hours
- [ ] Consider running smaller markets first (AU ~2,000, CA ~3,000) to validate at scale
- [ ] If a higher-tier Refinitiv subscription is available, restore `TR.F.*` fields
      for fuller income statement (EPS, SGA, R&D, tax rate, shares outstanding)
