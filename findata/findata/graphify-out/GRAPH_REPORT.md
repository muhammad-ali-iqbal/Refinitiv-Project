# Graph Report - .  (2026-06-04)

## Corpus Check
- Corpus is ~2,685 words - fits in a single context window. You may not need a graph.

## Summary
- 46 nodes · 73 edges · 9 communities (8 shown, 1 thin omitted)
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 6 edges (avg confidence: 0.87)
- Token cost: 5,200 input · 1,850 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Streamlit App & Query Layer|Streamlit App & Query Layer]]
- [[_COMMUNITY_Excel Sheet Parsing|Excel Sheet Parsing]]
- [[_COMMUNITY_Project Overview & Dependencies|Project Overview & Dependencies]]
- [[_COMMUNITY_Section Detection Logic|Section Detection Logic]]
- [[_COMMUNITY_DuckDB Schema Setup|DuckDB Schema Setup]]
- [[_COMMUNITY_Ingestion Pipeline Orchestration|Ingestion Pipeline Orchestration]]
- [[_COMMUNITY_File Ingestion & Upsert|File Ingestion & Upsert]]
- [[_COMMUNITY_Alias Seeding|Alias Seeding]]
- [[_COMMUNITY_RIC & Company Parsing|RIC & Company Parsing]]

## God Nodes (most connected - your core abstractions)
1. `parse_file()` - 14 edges
2. `ingest_file()` - 9 edges
3. `resolve_variable()` - 8 edges
4. `q()` - 7 edges
5. `ingest_folder()` - 6 edges
6. `setup_db()` - 5 edges
7. `seed_aliases()` - 5 edges
8. `_is_section_header()` - 5 edges
9. `facts table (DuckDB)` - 5 edges
10. `FinData Explorer Project` - 5 edges

## Surprising Connections (you probably didn't know these)
- `Refinitiv CF Export (source xlsx files)` --conceptually_related_to--> `parse_file()`  [INFERRED]
  README.md → ingestion/parser.py
- `Python Dependencies (duckdb, openpyxl, pandas, streamlit, plotly)` --conceptually_related_to--> `parse_file()`  [INFERRED]
  requirements.txt → ingestion/parser.py
- `Incremental Upsert Strategy` --rationale_for--> `ingest_file()`  [EXTRACTED]
  README.md → ingestion/ingest.py
- `FinData Explorer Project` --references--> `ingest_folder()`  [EXTRACTED]
  README.md → ingestion/ingest.py
- `Streamlit Financial Data Explorer UI` --conceptually_related_to--> `DuckDB Database (findata.duckdb)`  [INFERRED]
  app/app.py → README.md

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Full Ingestion Pipeline: ALIASES → seed_aliases → ingest_file → parse_file → facts table** — ingestion_aliases_aliases_dict, ingestion_ingest_seed_aliases, ingestion_ingest_ingest_file, ingestion_parser_parse_file, app_app_facts_table [EXTRACTED 1.00]
- **App Query Resolution: resolve_variable → aliases + facts → Variable/Company/Cross-Company modes** — app_app_resolve_variable, app_app_aliases_table, app_app_facts_table, app_app_variable_search_mode, app_app_company_view_mode, app_app_cross_company_mode [EXTRACTED 1.00]
- **Tidy DataFrame Contract shared between parser, ingest, and app** — ingestion_parser_tidy_dataframe, ingestion_ingest_ingest_file, app_app_facts_table [INFERRED 0.95]

## Communities (9 total, 1 thin omitted)

### Community 0 - "Streamlit App & Query Layer"
Cohesion: 0.33
Nodes (10): Company View Mode, Cross-Company Comparison Mode, facts table (DuckDB), get_con(), str, q(), app/app.py — Streamlit interface for searching and viewing financial variables., Given a search string, return matching variable names.     Priority: 1) exact al (+2 more)

### Community 1 - "Excel Sheet Parsing"
Cohesion: 0.33
Nodes (6): DataFrame, _extract_year_label (normalize year column labels), META_KEYS (metadata row labels), parse_file(), Parse all relevant sheets in a CF Export file.     Returns a tidy DataFrame with, SKIP_SHEETS (sheets excluded from parsing)

### Community 2 - "Project Overview & Dependencies"
Cohesion: 0.50
Nodes (5): Streamlit Financial Data Explorer UI, DuckDB Database (findata.duckdb), FinData Explorer Project, Refinitiv CF Export (source xlsx files), Python Dependencies (duckdb, openpyxl, pandas, streamlit, plotly)

### Community 3 - "Section Detection Logic"
Cohesion: 0.40
Nodes (4): bool, _is_section_header(), ingestion/parser.py  Parses a single Refinitiv CF Export .xlsx file into a norma, A section header has text in col A and nothing numeric in the rest.

### Community 4 - "DuckDB Schema Setup"
Cohesion: 0.50
Nodes (5): DuckDBPyConnection, DB_SCHEMA (DDL for facts, aliases, ingestion_log), ingest_folder(), str, setup_db()

### Community 6 - "File Ingestion & Upsert"
Cohesion: 0.50
Nodes (4): ingest_file(), ingestion_log table (DuckDB), Tidy DataFrame (ric, company_name, sheet, section, variable, year, value), Incremental Upsert Strategy

### Community 7 - "Alias Seeding"
Cohesion: 1.00
Nodes (3): aliases table (DuckDB), ALIASES dictionary (shorthand to full variable name), seed_aliases()

### Community 8 - "RIC & Company Parsing"
Cohesion: 0.67
Nodes (3): _parse_ric(), str, 'Pakistan State Oil Company Ltd (PSO.PSX)'      → ('Pakistan State Oil Company L

## Knowledge Gaps
- **6 isolated node(s):** `bool`, `DataFrame`, `DB_SCHEMA (DDL for facts, aliases, ingestion_log)`, `ingestion_log table (DuckDB)`, `SKIP_SHEETS (sheets excluded from parsing)` (+1 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **1 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `parse_file()` connect `Excel Sheet Parsing` to `Project Overview & Dependencies`, `Section Detection Logic`, `Ingestion Pipeline Orchestration`, `File Ingestion & Upsert`, `RIC & Company Parsing`?**
  _High betweenness centrality (0.465) - this node is a cross-community bridge._
- **Why does `ingest_file()` connect `File Ingestion & Upsert` to `Streamlit App & Query Layer`, `Excel Sheet Parsing`, `DuckDB Schema Setup`, `Ingestion Pipeline Orchestration`?**
  _High betweenness centrality (0.407) - this node is a cross-community bridge._
- **Why does `facts table (DuckDB)` connect `Streamlit App & Query Layer` to `File Ingestion & Upsert`?**
  _High betweenness centrality (0.274) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `parse_file()` (e.g. with `Refinitiv CF Export (source xlsx files)` and `Python Dependencies (duckdb, openpyxl, pandas, streamlit, plotly)`) actually correct?**
  _`parse_file()` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `app/app.py — Streamlit interface for searching and viewing financial variables.`, `Given a search string, return matching variable names.     Priority: 1) exact al`, `ingestion/aliases.py  Maps common shorthand codes → full Refinitiv variable name` to the rest of the system?**
  _15 weakly-connected nodes found - possible documentation gaps or missing edges._