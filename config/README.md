# config/

All tunable parameters. You should not need to touch any other file for routine adjustments.

## settings.py

| Setting | Default | What it controls |
|---|---|---|
| `OUTPUT_ROOT` | `~/Desktop/Data` | Root folder for all output |
| `COUNTRIES` | 10 countries | `"Folder name": "ISO-3 code"` pairs |
| `HISTORY_YEARS` | 10 | Years of annual history per company |
| `STATEMENT_TYPE` | `"STD"` | Refinitiv normalisation standard (see below) |
| `BATCH_SIZE` | 50 | RICs per API call for summary/index fetches |
| `DELAY_BETWEEN_BATCHES` | 1.5s | Pause between batch calls |
| `DELAY_BETWEEN_COMPANIES` | 0.5s | Pause between per-company extractions |
| `MAX_RETRIES` | 3 | Retry attempts before marking a company failed |
| `RETRY_BACKOFF` | 5.0s | Initial wait on retry (doubles each attempt) |
| `CHECKPOINT_FILE` | `Data/_pipeline_checkpoint.json` | Crash-recovery state |

## STATEMENT_TYPE values

| Code | Standard | Best for |
|---|---|---|
| `STD` | Refinitiv standardised (**recommended**) | Cross-country comparisons |
| `IAS` | IFRS | European/Asian/international companies |
| `GAAP` | US GAAP | US-listed companies |
| `ORI` | As-reported | Exact filing line items |

## Adding a country

```python
"South Korea": "KOR",
```

Country codes follow ISO 3166-1 alpha-3. Full list: [LSEG Eikon Data API docs](https://developers.lseg.com/en/api-catalog/eikon/eikon-data-api).

## Note on FINANCIAL_FIELDS

This setting no longer exists. The pipeline now fetches complete standardised statements using Refinitiv's `TR.F.*` field namespace. All line item definitions live in `pipeline/fetcher.py` under `INCOME_STATEMENT_FIELDS`, `BALANCE_SHEET_FIELDS`, and `CASH_FLOW_FIELDS`.
