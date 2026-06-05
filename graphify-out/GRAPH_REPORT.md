# Graph Report - .  (2026-06-04)

## Corpus Check
- Corpus is ~13,532 words - fits in a single context window. You may not need a graph.

## Summary
- 78 nodes · 118 edges · 13 communities (11 shown, 2 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 12 edges (avg confidence: 0.9)
- Token cost: 8,500 input · 2,800 output

## Community Hubs (Navigation)
- [[_COMMUNITY_LSEG Data Fetcher|LSEG Data Fetcher]]
- [[_COMMUNITY_Excel Report Writer|Excel Report Writer]]
- [[_COMMUNITY_Pipeline Orchestrator|Pipeline Orchestrator]]
- [[_COMMUNITY_Config and Documentation|Config and Documentation]]
- [[_COMMUNITY_Financial Statement Fields|Financial Statement Fields]]
- [[_COMMUNITY_LSEG API Migration|LSEG API Migration]]
- [[_COMMUNITY_Package Root|Package Root]]

## God Nodes (most connected - your core abstractions)
1. `run()` - 16 edges
2. `write_workbook()` - 11 edges
3. `get_financials()` - 9 edges
4. `_write_statement_sheet()` - 6 edges
5. `_apply_header()` - 5 edges
6. `get_companies_for_country()` - 5 edges
7. `_fetch_statement()` - 5 edges
8. `load_checkpoint()` - 5 edges
9. `save_checkpoint()` - 5 edges
10. `setup_logger()` - 5 edges

## Surprising Connections (you probably didn't know these)
- `Config README` --references--> `STATEMENTS Dict`  [EXTRACTED]
  config/README.md → pipeline/fetcher.py
- `Tutorial Screenshot — Refinitiv Eikon Financial Summary UI` --conceptually_related_to--> `Refinitiv TR.F.* Standardised Field Namespace`  [INFERRED]
  Tutorial.png → pipeline/fetcher.py
- `Rate Limit Settings (BATCH_SIZE, DELAY_*, MAX_RETRIES, RETRY_BACKOFF)` --rationale_for--> `get_companies_for_country()`  [INFERRED]
  config/settings.py → pipeline/fetcher.py
- `Rate Limit Settings (BATCH_SIZE, DELAY_*, MAX_RETRIES, RETRY_BACKOFF)` --rationale_for--> `get_financials()`  [INFERRED]
  config/settings.py → pipeline/fetcher.py
- `setup_logger()` --shares_data_with--> `OUTPUT_ROOT`  [INFERRED]
  utils/logger.py → config/settings.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Core Pipeline Data Flow: Fetch → Orchestrate → Write** — pipeline_fetcher_get_financials, pipeline_orchestrator_run, pipeline_excel_writer_write_workbook [EXTRACTED 1.00]
- **Crash Recovery Flow: Load → Check → Save → Reset** — utils_checkpoint_load_checkpoint, utils_checkpoint_save_checkpoint, utils_checkpoint_reset, pipeline_orchestrator_run [EXTRACTED 1.00]
- **Financial Statement Field Definitions (Income, Balance Sheet, Cash Flow)** — pipeline_fetcher_income_fields, pipeline_fetcher_balance_fields, pipeline_fetcher_cashflow_fields, pipeline_fetcher_statements [EXTRACTED 1.00]

## Communities (13 total, 2 thin omitted)

### Community 0 - "LSEG Data Fetcher"
Cohesion: 0.14
Nodes (17): Single-File API Isolation (fetcher.py only imports lseg-data), Rate Limit Settings (BATCH_SIZE, DELAY_*, MAX_RETRIES, RETRY_BACKOFF), STATEMENT_TYPE, close_session(), _fetch_statement(), get_companies_for_country(), get_financials(), open_session() (+9 more)

### Community 1 - "Excel Report Writer"
Cohesion: 0.19
Nodes (16): Live Excel Cross-Sheet Formula Ratios, int, _apply_header(), _write_ratios_sheet(), _write_statement_sheet(), _apply_data_cell(), _apply_header(), DataFrame (+8 more)

### Community 2 - "Pipeline Orchestrator"
Cohesion: 0.22
Nodes (14): CHECKPOINT_FILE, COUNTRIES, OUTPUT_ROOT, _company_path(), _index_path(), str, pipeline/orchestrator.py — Drives the full pipeline loop.  For each country → ge, Main pipeline entry point.      Args:         app_key:   LSEG / Eikon API key (4 (+6 more)

### Community 3 - "Config and Documentation"
Cohesion: 0.20
Nodes (7): Crash Recovery / Checkpoint Pattern, config/settings.py — All tunable parameters for the pipeline. Edit this file to, Config README, Main README — Pipeline Overview, Utils README, utils/checkpoint.py — Simple JSON-backed crash recovery., utils/logger.py — Configures logging to both console and file.

### Community 4 - "Financial Statement Fields"
Cohesion: 0.47
Nodes (6): Refinitiv TR.F.* Standardised Field Namespace, BALANCE_SHEET_FIELDS, CASH_FLOW_FIELDS, INCOME_STATEMENT_FIELDS, STATEMENTS Dict, Tutorial Screenshot — Refinitiv Eikon Financial Summary UI

## Knowledge Gaps
- **7 isolated node(s):** `str`, `Refinitiv Pipeline Project Root`, `COUNTRIES`, `STATEMENT_TYPE`, `LSEG Data API (lseg-data)` (+2 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **2 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `run()` connect `Pipeline Orchestrator` to `LSEG Data Fetcher`, `Excel Report Writer`?**
  _High betweenness centrality (0.259) - this node is a cross-community bridge._
- **Why does `write_workbook()` connect `Excel Report Writer` to `Pipeline Orchestrator`, `Financial Statement Fields`?**
  _High betweenness centrality (0.239) - this node is a cross-community bridge._
- **Why does `get_financials()` connect `LSEG Data Fetcher` to `Pipeline Orchestrator`?**
  _High betweenness centrality (0.117) - this node is a cross-community bridge._
- **What connects `config/settings.py — All tunable parameters for the pipeline. Edit this file to`, `pipeline/excel_writer.py — Writes one .xlsx workbook per company.  Four sheets:`, `Write a single financial statement to a worksheet.` to the rest of the system?**
  _25 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `LSEG Data Fetcher` be split into smaller, more focused modules?**
  _Cohesion score 0.14035087719298245 - nodes in this community are weakly interconnected._