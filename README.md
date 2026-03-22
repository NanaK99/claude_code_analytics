# Claude Code Analytics Platform

## Project Overview

The Claude Code Usage Analytics Platform ingests approximately 454,000 telemetry events exported from AWS CloudWatch as a JSONL file, along with an employee CSV containing engineer metadata, and loads them into a local DuckDB columnar database. A FastAPI backend exposes the analytics data over a REST API, and a multi-tab Streamlit dashboard consumes that API to provide interactive exploration of cost, token consumption, team activity patterns, and tool behavior — giving engineering managers and leads a self-hosted view of how their teams use Claude Code.

## Architecture

```
ingest.py ──▶ data_generation/output/telemetry_logs.jsonl  ──▶  db/analytics.duckdb
              data_generation/output/employees.csv                      │
                                                                         ▼
                                                           uvicorn api:app  (FastAPI)
                                                                         │
                                                                         ▼
                                                          streamlit run app.py
```

`ingest.py` is idempotent: it drops and recreates all tables on every run, so re-running it against updated source files is safe. `app.py` is read-only and never touches the database directly — all data fetches go through the API.

## Setup

```bash
# 1. Create and activate environment
conda env create -f environment.yml
conda activate provectus_task

# 2. Ingest data (~1-2 minutes, creates db/analytics.duckdb)
python ingest.py

# 3. Copy .env.sample and set your API key
cp .env.sample .env
# Edit .env — set API_KEY to any secret string (e.g. dev-key)

# 4. Start the API server (keep running in a separate terminal)
uvicorn api:app --reload

# 5. Launch dashboard
streamlit run app.py
```

## Dashboard Overview

The dashboard is organized into six tabs:

| Tab | Contents |
|-----|----------|
| **Overview** | KPI cards (total cost, sessions, engineers, error rate, avg session duration, avg prompts/session) and a daily sessions trend chart |
| **Cost & Tokens** | Cost over time broken down by practice and level, avg cost per session trend, token breakdown, model distribution, and cache hit rate / savings |
| **Team & Engineers** | Sessions and cost aggregated by practice, level, and location; top-10 engineers table |
| **Activity Patterns** | Hour × day-of-week heatmap, sessions by day of week, and a business hours vs. after-hours split |
| **Tool Behavior** | Tool call frequency, accept/reject rates per tool, average execution times, and tool success rates |
| **Session Intelligence** | Session duration distribution (log scale), API latency by model, error breakdown by status code, avg cost by seniority level, and session cost distribution by practice |

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| duckdb | 1.2.1 | Columnar analytics database |
| streamlit | 1.43.2 | Interactive web dashboard |
| pandas | 2.2.3 | DataFrame processing |
| plotly | 5.24.1 | Interactive charts |
| tqdm | 4.67.1 | ETL progress bar |
| pytest | 8.3.5 | Test runner |
| pydantic | >=2.0 | Request/response validation |
| fastapi | >=0.115.0 | REST API framework |
| uvicorn | >=0.34.0 | ASGI server |
| requests | >=2.32.0 | HTTP client for Streamlit → API calls |
| python-dotenv | >=1.0.0 | `.env` file loading |

## Running Tests

```bash
pytest tests/ -v
```

38 tests cover schema validation, the event parser, the ingest pipeline, and all query functions.

## LLM Usage Log

Claude Code (`claude-sonnet-4-6`) was used throughout this project to design the architecture, write implementation plans, and implement all code via a subagent-driven development workflow.

Example prompts used during development:

- "Design a local analytics platform for Claude Code telemetry data using DuckDB and Streamlit"
- "Implement chunked insertion into DuckDB with per-buffer flushing at CHUNK_SIZE=10,000"
- "Write analytics query functions for a 6-tab Streamlit dashboard with sidebar filters"
- "Build a FastAPI backend with 26 endpoints wrapping the DuckDB query layer"
- "Migrate app.py to consume the FastAPI backend via HTTP instead of querying DuckDB directly"

All generated code was validated through automated test suites (38 tests), spec compliance reviews, code quality reviews, and manual verification against the real 454K-event dataset.
