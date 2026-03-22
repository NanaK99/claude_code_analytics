# CLAUDE.md

## Environment

Always use the `provectus_task` conda environment for all commands:

```bash
conda run -n provectus_task <command>
# e.g.
conda run -n provectus_task pytest tests/ -v
conda run -n provectus_task python ingest.py
conda run -n provectus_task uvicorn api:app --reload
conda run -n provectus_task streamlit run app.py
```

Never use bare `python`, `pytest`, or `pip` — always prefix with `conda run -n provectus_task`.

## Project Structure

| Path | Role |
|------|------|
| `ingest.py` | ETL entry point — run once to populate `db/analytics.duckdb` |
| `api.py` | FastAPI entry point — `uvicorn api:app` re-exports `src.api.main.app` |
| `app.py` | Streamlit dashboard — 6 tabs, reads data from FastAPI via HTTP |
| `src/schema.py` | `init_db(conn)` — creates all 6 tables |
| `src/parser.py` | `parse_event(body, attrs, line_num, event_idx)` — dispatches to 5 handlers |
| `src/queries.py` | 25 query functions, all `(conn, filters) -> pd.DataFrame or scalar` |
| `src/api/main.py` | FastAPI app — mounts 6 routers under `/api/v1`, manages DuckDB lifespan |
| `src/api/auth.py` | API key validation via `X-API-Key` header (403 on failure) |
| `src/api/schemas.py` | Pydantic request/response models for all 26 endpoints |
| `src/api/deps.py` | FastAPI dependency: returns shared DuckDB connection from app state |
| `src/api/routers/` | 6 router modules: `overview`, `costs`, `team`, `activity`, `tools`, `sessions` |
| `.env` | Local env vars (gitignored) — `API_URL`, `API_KEY` |
| `.env.sample` | Committed template for `.env` |
| `db/analytics.duckdb` | Generated database (gitignored) — recreate with `python ingest.py` |
| `data_generation/output/` | Source data (gitignored) — do not modify |

## Key Invariants

- `db/`, `data_generation/output/`, and `.env` are gitignored — never commit them
- `docs/superpowers/` is gitignored — never commit it
- DuckDB column insertion requires explicit column names (`SELECT col1, col2 FROM df`), never `SELECT *` — pandas alphabetizes columns but DuckDB expects schema order
- All query functions in `src/queries.py` accept `(conn, filters: dict)` and return `pd.DataFrame` or scalar; no rendering logic inside them
- `ingest.py` is idempotent — drops and recreates all tables on each run
- `app.py` connects to the FastAPI backend via HTTP; it never imports DuckDB or `src.queries` directly
- `API_KEY` must match in both the API server env and the Streamlit `.env` — the API returns 403 otherwise
- The API server must be running before launching `app.py`

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
| [knowledge/api.md](knowledge/api.md) | FastAPI reference — all 26 endpoints, FiltersRequest schema, auth, error codes |
