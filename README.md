# Refinitiv Eikon Data Pipeline

Automated pipeline to extract full standardised financial statements for all listed companies across 50+ countries from Refinitiv Eikon, stored as structured Excel workbooks.

---

## Output folder structure

```
Desktop/
└── Data/
    ├── _pipeline.log
    ├── _pipeline_checkpoint.json
    │
    ├── United States/
    │   ├── _Index.xlsx                    ← All US companies, one row each
    │   ├── Apple Inc/
    │   │   └── Apple Inc.xlsx             ← 4 sheets: IS | BS | CF | Ratios
    │   ├── Microsoft Corp/
    │   │   └── Microsoft Corp.xlsx
    │   └── ...
    └── ...
```

---

## What each workbook contains

Each company gets one `.xlsx` file with **four sheets**:

| Sheet | Contents |
|---|---|
| **Income Statement** | Revenue, Gross Profit, EBIT, EBITDA, Net Income, D&A, Interest Expense — 10 years annual |
| **Balance Sheet** | Cash, Current Assets, Total Assets, Current Liabilities, LT Debt, Total Debt, Total Liabilities, Total Equity, Retained Earnings, Book Value/Share — 10 years annual |
| **Cash Flow** | Free Cash Flow, Net Change in Cash — 10 years annual |
| **Ratios** | Live Excel formulas: EBITDA Margin, Net Margin, Debt/Equity, Net Debt/EBITDA, Asset Turnover, FCF Conversion, FCF Margin |

Data uses the `TR.*` field namespace (compatible with the IBA API subscription).
All values are in **USD millions** (`Scale=6`), annual frequency.

> **Note:** The `TR.F.*` standardised namespace (which adds EPS, SGA, R&D, tax rate, etc.)
> requires a separate Refinitiv Fundamentals subscription not included in the current key.
> See `CHANGELOG.md` for details.

---

## Prerequisites

1. **Refinitiv Eikon / Workspace** desktop app — installed, open, and logged in
2. **Python 3.10+**
3. **Eikon API key** — generate inside Eikon: `Top-right menu → API → Create API key`

---

## Installation

```bash
pip install lseg-data openpyxl pandas
```

---

## Setup

1. Open `config/settings.py`:
   - Set `OUTPUT_ROOT` to the target desktop path
   - Add/remove countries in `COUNTRIES`
   - Set `HISTORY_YEARS` (default: 10)
   - Set `STATEMENT_TYPE` — `"STD"` (recommended), `"IAS"`, `"GAAP"`, or `"ORI"`

2. Open `run_pipeline.py` and paste your LSEG API key into `LSEG_APP_KEY`.

---

## Running

```bash
cd refinitiv_pipeline
python run_pipeline.py
```

**Test on one country first** — a 5-company limit is active in `orchestrator.py`:
```python
# pipeline/orchestrator.py — remove this line for a full run:
companies = companies[:5]
```

---

## Crash recovery

Re-run `run_pipeline.py` at any time — it skips companies already written and retries failed ones. To restart from scratch:
```python
from utils.checkpoint import reset
reset()
```

---

## Statement types explained

| Code | Standard | Best for |
|---|---|---|
| `STD` | Refinitiv standardised | Cross-country comparisons — normalises all filings |
| `IAS` | IFRS | European, Asian, and international companies |
| `GAAP` | US GAAP | US-listed companies |
| `ORI` | As-reported | Getting exactly what the company filed |

---

## Ratios sheet — what's calculated

All ratios are live Excel formulas — they recalculate if you edit the source sheets.

**Profitability:** Gross Margin, EBITDA Margin, EBIT Margin, Net Profit Margin, ROE, ROA, ROIC  
**Liquidity:** Current Ratio, Quick Ratio, Cash Ratio  
**Leverage:** Debt/Equity, Net Debt/EBITDA, Interest Coverage, Debt/Assets  
**Efficiency:** Asset Turnover, Receivables Turnover, Inventory Turnover  
**Cash Flow Quality:** FCF Margin, FCF/Net Income, CapEx/Revenue, Cash Conversion

---

## Rate limits & runtime

Eikon allows ~5 req/s and ~300 req/min. Each company now makes **3 API calls** (one per statement) so the default delay is 0.5s between companies. For 5,000+ companies expect **12–16 hours** — run overnight.

Increase `DELAY_BETWEEN_COMPANIES` in `config/settings.py` if you see `EikonError 400.3001`.

---

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `SessionError: No proxy found` | Eikon/Workspace not running | Open Eikon/Workspace and log in |
| `LDError 400.3001` | Rate limit hit | Increase `DELAY_BETWEEN_COMPANIES` in settings.py |
| `LDError: access denied` | Field not in subscription | See CHANGELOG.md — `TR.F.*` fields need Fundamentals subscription |
| Empty statement sheet | No data for that RIC | Normal for some companies |
| Ratios show `N/A` | Required field not in current field set | Expected — see CHANGELOG.md |
| Ratios show empty | Formula denominator is zero | Normal — IFERROR handles it gracefully |
