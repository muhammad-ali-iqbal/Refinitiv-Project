# utils/

Shared utilities used across the pipeline. Neither module has any Eikon or Excel dependency — they are pure Python.

---

## checkpoint.py

Saves pipeline progress to a JSON file so a crash or interruption never requires restarting from scratch.

### Checkpoint file format

```json
{
  "completed": ["USA::AAPL.O", "USA::MSFT.O", "GBR::SHEL.L"],
  "failed":    {"USA::XYZ.N": "EikonError 400.3001: backend overloaded"}
}
```

Keys are `"COUNTRY_CODE::RIC"` strings. The file is written after every single company so the worst-case loss from a crash is one company.

### Functions

| Function | Description |
|---|---|
| `mark_done(country_code, ric)` | Adds a company to `completed`, removes it from `failed` |
| `mark_failed(country_code, ric, error)` | Adds a company to `failed` with the error message |
| `is_done(country_code, ric) → bool` | Returns `True` if the company has been successfully written |
| `summary() → dict` | Returns counts of completed and failed companies |
| `reset()` | Deletes the checkpoint file — restarts the pipeline from scratch |

### Resuming after a crash

Simply re-run `run_pipeline.py`. The orchestrator calls `is_done()` before every company and skips those already in `completed`.

### Retrying failed companies

Failed companies stay in the checkpoint until they are successfully processed. Re-running the pipeline automatically retries them — the orchestrator only skips `completed` entries, not `failed` ones.

To inspect which companies failed and why:

```python
from utils.checkpoint import summary
print(summary())
```

---

## logger.py

Provides a consistent logger instance for every module, writing to both the terminal and a rolling log file.

### Log file location

```
Data/_pipeline.log
```

The file is created automatically alongside the output data. It captures `DEBUG`-level messages (including per-company API call details) that are too noisy for the terminal, which shows only `INFO` and above.

### Usage in any module

```python
from utils.logger import get_logger
log = get_logger(__name__)

log.info("Starting extraction…")
log.debug("Detailed call info")
log.warning("Partial error returned")
log.error("Company failed entirely")
```

### Log format

```
2025-06-02 14:32:01  INFO      pipeline.orchestrator  COUNTRY: United States (USA)
2025-06-02 14:32:03  INFO      pipeline.fetcher       → 4,312 companies found in USA
2025-06-02 14:32:04  INFO      pipeline.orchestrator  [1/4312] Apple Inc (AAPL.O)
2025-06-02 14:32:05  DEBUG     pipeline.fetcher       Fetching financials for AAPL.O
```
