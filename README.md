# Claude Code Analytics Platform

## Project Overview

The Claude Code Usage Analytics Platform ingests approximately 454,000 telemetry events exported from AWS CloudWatch as a JSONL file, along with an employee CSV containing engineer metadata, and loads them into a local DuckDB columnar database. A multi-tab Streamlit dashboard then provides interactive exploration of cost, token consumption, team activity patterns, and tool behavior — giving engineering managers and leads a self-hosted view of how their teams use Claude Code.

## Architecture

```
ingest.py ──▶ data_generation/output/telemetry_logs.jsonl  ──▶  db/analytics.duckdb
              data_generation/output/employees.csv                      │
                                                                         ▼
                                                          streamlit run app.py
```

`ingest.py` is idempotent: it drops and recreates all tables on every run, so re-running it against updated source files is safe. `app.py` is read-only and never modifies the database.

## Setup

```bash
# Create and activate environment
conda env create -f environment.yml
conda activate provectus_task

# Ingest data (~1-2 minutes, creates db/analytics.duckdb)
python ingest.py

# Launch dashboard
streamlit run app.py
```

## Dashboard Overview

The dashboard is organized into five tabs:

| Tab | Contents |
|-----|----------|
| **Overview** | KPI cards (total cost, sessions, engineers, error rate) and a daily sessions trend chart |
| **Cost & Tokens** | Cost over time broken down by practice and level, token breakdown, model distribution, and cache hit rate |
| **Team & Engineers** | Sessions and cost aggregated by practice, level, and location; top-10 engineers table |
| **Activity Patterns** | Hour × day-of-week heatmap and a business hours vs. after-hours split |
| **Tool Behavior** | Tool call frequency, accept/reject rates per tool, and average execution times |

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| duckdb | 1.2.1 | Columnar analytics database |
| streamlit | 1.43.2 | Interactive web dashboard |
| pandas | 2.2.3 | DataFrame processing |
| plotly | 5.24.1 | Interactive charts |
| tqdm | 4.67.1 | ETL progress bar |
| pytest | 8.3.5 | Test runner |

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
- "Write analytics query functions for a 5-tab Streamlit dashboard with sidebar filters"

All generated code was validated through automated test suites (38 tests), spec compliance reviews, code quality reviews, and manual verification against the real 454K-event dataset.
