# FinData Explorer

Search and visualise financial variables from Refinitiv across companies worldwide.

---

## Setup

```bash
pip install -r requirements.txt
```

---

## Step 1 — Fetch data from Refinitiv (automated)

Requires **LSEG Workspace open and signed in**. Fetches 51 fields across 7 groups (financials,
valuation, ESG, estimates) directly into DuckDB — no manual export needed.

```bash
python -m ingestion.fetch --db data/findata.duckdb --index "0#.KSE"
```

| Part | Meaning |
|---|---|
| `python -m ingestion.fetch` | Runs `ingestion/fetch.py` as a module |
| `--db data/findata.duckdb` | Target database (same file the app reads) |
| `--index "0#.KSE"` | Refinitiv index RIC — `0#` means "constituents of"; `0#.KSE` = KSE Composite (100 companies) |

**Other universe examples:**

| Index | RIC |
|---|---|
| KSE-100 | `0#KSE100.PSX` |
| S&P 500 | `0#.SPX` |
| MSCI World | `0#MSCIWORLD` |

- Resumable — re-running skips already-fetched fields. Use `--reset` to force a full re-fetch.
- To fetch specific companies instead of an index: `--rics "PSO.PSX,LUCK.PSX"`
- API key is read from `.env` automatically (set `EIKON_APP_KEY`).

### Field groups fetched

| Group | Fields |
|---|---|
| Income Statement | Revenue, Gross Profit, EBITDA, EBIT, Net Income, EPS |
| Balance Sheet | Total Assets, Cash, Debt, Common Equity |
| Cash Flow | Operating CF, CapEx, Free Cash Flow |
| Valuation | Price, Market Cap, EV, P/E, P/B, P/TBV, P/S, P/CF, P/FCF, EV/EBITDA, EV/Sales, EV/CFO, Div Yield, FCF Yield, PEG |
| Financial Ratios | ROE, ROA, ROIC, Gross/EBITDA/Operating/Net Margins |
| ESG | Combined score, E/S/G pillar scores, 9 sub-scores |
| Estimates | Consensus Revenue, EBITDA, Net Income, EPS, Price Target |

---

## Step 1 (alternative) — Ingest manual CF Export files

If you have manually exported CF Export `.xlsx` files from Workspace:

```bash
python -m ingestion.ingest --source "C:\path\to\xlsx\folder" --db data/findata.duckdb
```

- Runs once to build the database. Re-run whenever new files arrive — it upserts, never duplicates.
- Progress is logged to the terminal.

---

## Step 2 — Launch the app

```bash
python -m streamlit run app/app.py
```

Opens in your browser at `http://localhost:8501`.

---

## App modes

**Variable Search** — Type a shorthand (PTBV, EV, ROE) or partial name. See a time-series chart and data table across all companies. Download as CSV.

**Company View** — Select a company, filter by sheet or variable name, chart any metric over time.

**Cross-Company** — Pick a variable + year, get all companies ranked by that value as a bar chart.

---

## Adding aliases

Edit `ingestion/aliases.py` to add new shorthand → full variable name mappings:

```python
"MY_CODE": "Full Refinitiv Variable Name As It Appears In The Sheet",
```

Then re-seed by running any ingestion command (aliases are inserted on every run).

---

## Folder structure

```
findata/
├── ingestion/
│   ├── fetch.py        ← Eikon API fetcher → writes directly to DuckDB
│   ├── parser.py       ← Reads one .xlsx → tidy DataFrame (manual path)
│   ├── ingest.py       ← Loops all .xlsx files → writes to DuckDB (manual path)
│   └── aliases.py      ← Shorthand → full variable name mappings
├── app/
│   └── app.py          ← Streamlit UI
├── data/
│   └── findata.duckdb  ← Database (created on first run)
├── .env                ← EIKON_APP_KEY (not committed to version control)
└── requirements.txt
```

---

## Troubleshooting

| Issue | Fix |
|---|---|
| `Database not found` | Run the fetch or ingest step first |
| `Cannot open file … used by another process` | Close the Streamlit app before running fetch |
| `No RICs returned for index` | Verify the index RIC in Workspace; try `0#KSE100.PSX` or `0#.PSX` |
| Variable not found | Check `aliases.py` or search by partial name |
| Field returns no data | Verify the TR. code in Workspace → Data Item Browser |
| Wrong values | Financial statement values are in Millions, native currency (PKR for PSX) |
| New year columns not appearing | Re-run fetch — it does a full refresh per (ric, field) |
