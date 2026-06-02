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
| **Income Statement** | ~26 line items — Revenue → EPS, 10 years of annual data |
| **Balance Sheet** | ~31 line items — Current/Non-current Assets, Liabilities, Equity |
| **Cash Flow** | ~22 line items — Operating, Investing, Financing, FCF |
| **Ratios** | 20 derived ratios as live Excel formulas cross-referencing the 3 statement sheets |

All data uses Refinitiv's **standardised (`STD`) field namespace** (`TR.F.*`) — meaning line items are normalised across all companies regardless of whether they file under US GAAP, IFRS, or local standards.

---

## Prerequisites

1. **Refinitiv Eikon / Workspace** desktop app — installed, open, and logged in
2. **Python 3.10+**
3. **Eikon API key** — generate inside Eikon: `Top-right menu → API → Create API key`

---

## Installation

```bash
pip install eikon pandas xlsxwriter
```

---

## Setup

1. Open `config/settings.py`:
   - Set `OUTPUT_ROOT` to the target desktop path
   - Add/remove countries in `COUNTRIES`
   - Set `HISTORY_YEARS` (default: 10)
   - Set `STATEMENT_TYPE` — `"STD"` (recommended), `"IAS"`, `"GAAP"`, or `"ORI"`

2. Open `run_pipeline.py` and paste your Eikon API key, or export it:
   ```bash
   export EIKON_APP_KEY="your_40_char_key"   # macOS/Linux
   set EIKON_APP_KEY=your_40_char_key         # Windows CMD
   ```

---

## Running

```bash
cd refinitiv_pipeline
python run_pipeline.py
```

**Test on one country first:**
```python
# In run_pipeline.py:
COUNTRIES_OVERRIDE = {"United States": "USA"}
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
| `EikonError: No proxy found` | Eikon not running | Open Eikon and log in |
| `EikonError 400.3001` | Rate limit hit | Increase delays in settings.py |
| `EikonError 400.2001` | Invalid API key | Check key in Eikon API settings |
| Empty statement sheet | No data for that RIC | Normal for some companies — other sheets may still have data |
| Ratios show `—` | Formula denominator is zero or missing | Normal — IFERROR handles it gracefully |
