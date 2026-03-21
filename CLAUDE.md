# CLAUDE.md

## Environment

Always use the `provectus_task` conda environment for all commands:

```bash
conda run -n provectus_task <command>
# e.g.
conda run -n provectus_task pytest tests/ -v
conda run -n provectus_task python ingest.py
conda run -n provectus_task streamlit run app.py
```

Never use bare `python`, `pytest`, or `pip` — always prefix with `conda run -n provectus_task`.

## Project Structure

| Path | Role |
|------|------|
| `ingest.py` | ETL entry point — run once to populate `db/analytics.duckdb` |
| `app.py` | Streamlit dashboard — 5 tabs, read-only DuckDB queries |
| `src/schema.py` | `init_db(conn)` — creates all 6 tables |
| `src/parser.py` | `parse_event(body, attrs, line_num, event_idx)` — dispatches to 5 handlers |
| `src/queries.py` | 17 query functions, all `(conn, filters) -> pd.DataFrame or scalar` |
| `db/analytics.duckdb` | Generated database (gitignored) — recreate with `python ingest.py` |
| `data_generation/output/` | Source data (gitignored) — do not modify |

## Key Invariants

- `db/` and `data_generation/output/` are gitignored — never commit them
- `docs/superpowers/` is gitignored — never commit it
- DuckDB column insertion requires explicit column names (`SELECT col1, col2 FROM df`), never `SELECT *` — pandas alphabetizes columns but DuckDB expects schema order
- All query functions in `src/queries.py` accept `(conn, filters: dict)` and return `pd.DataFrame` or scalar; no rendering logic inside them
- `ingest.py` is idempotent — drops and recreates all tables on each run
- `app.py` connects to DuckDB in read-only mode via `@st.cache_resource`

## Running Tests

```bash
conda run -n provectus_task pytest tests/ -v
```

38 tests covering: schema (4), parser (8), ingest (5), queries (21).

## Knowledge Docs

Project reference documents are stored in the `knowledge/` directory.
Always check there first for context before exploring the codebase.

| File | Contents |
|------|----------|
| [knowledge/data_format.md](knowledge/data_format.md) | Dataset format reference — file structure, all event types with examples, session flow, generation method |
