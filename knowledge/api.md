# FastAPI Analytics API Reference

## Overview

The analytics API is a FastAPI service that exposes all dashboard query functions over HTTP.
`app.py` consumes it; the DuckDB database is never accessed directly by Streamlit.

| Property | Value |
|----------|-------|
| Entry point | `api.py` → `uvicorn api:app` |
| Base URL | `http://localhost:8000` (configurable via `API_URL` env var) |
| Auth | `X-API-Key` request header |
| Content type | `application/json` |
| HTTP method | All endpoints use **POST** |
| Interactive docs | `http://localhost:8000/docs` |

## Startup

```bash
# Requires API_KEY set in environment (or .env file)
conda run -n provectus_task uvicorn api:app --reload
```

Environment variables read by the API server at startup:

| Variable | Default | Description |
|----------|---------|-------------|
| `API_KEY` | _(required)_ | Secret used to authenticate all requests |
| `DB_PATH` | `db/analytics.duckdb` | Path to the DuckDB database file |

## FiltersRequest

All endpoints accept the same JSON body:

```json
{
  "date_start": "2025-12-03",
  "date_end":   "2026-02-01",
  "practices":  [],
  "levels":     [],
  "locations":  []
}
```

| Field | Type | Default | Validation |
|-------|------|---------|------------|
| `date_start` | `string` (ISO date) | _(required)_ | Must be ≤ `date_end` |
| `date_end` | `string` (ISO date) | _(required)_ | Must be ≥ `date_start` |
| `practices` | `string[]` | `[]` (all) | Valid values: `Platform Engineering`, `Data Engineering`, `ML Engineering`, `Backend Engineering`, `Frontend Engineering` |
| `levels` | `string[]` | `[]` (all) | Valid values: `L1`–`L10` |
| `locations` | `string[]` | `[]` (all) | Valid values: `United States`, `Germany`, `United Kingdom`, `Poland`, `Canada` |

Empty arrays mean "no filter — include all".

## Error Responses

| Status | Meaning |
|--------|---------|
| 403 | Invalid or missing `X-API-Key` header |
| 422 | Pydantic validation failure on `FiltersRequest` (e.g. `date_start > date_end`) |
| 500 | Internal server error — check API server logs |

---

## Endpoint Reference

### Overview — `/api/v1/overview`

#### `POST /kpi-metrics`
Returns top-level KPI scalars.

**Response:**
```json
{
  "total_sessions":    5000,
  "active_engineers":  100,
  "total_cost":        1234.56,
  "error_rate":        0.012
}
```

#### `POST /session-kpis`
Returns session-level aggregate metrics.

**Response:**
```json
{
  "avg_duration_mins":       12.4,
  "avg_prompts_per_session": 8.1
}
```

#### `POST /daily-sessions`
Returns daily session counts over the date range.

**Response:** `[{"date": "2025-12-03", "session_count": 42}, ...]`

#### `POST /cache-savings`
Returns estimated dollar savings from prompt caching. Based on Sonnet 4.6 pricing applied to all models.

**Response:** `{"cache_savings_usd": 890.12}`

---

### Costs — `/api/v1/costs`

#### `POST /by-practice`
Daily cost broken down by engineering practice.

**Response:** `[{"date": "2025-12-03", "practice": "Data Engineering", "total_cost": 12.34}, ...]`

#### `POST /by-level`
Daily cost broken down by seniority level.

**Response:** `[{"date": "2025-12-03", "level": "L4", "total_cost": 8.90}, ...]`

#### `POST /avg-cost-trend`
Daily average cost per session.

**Response:** `[{"date": "2025-12-03", "avg_cost_per_session": 0.24}, ...]`

#### `POST /cache-hit-rate`
Fraction of input tokens served from cache.

**Response:** `{"cache_hit_rate": 0.72}`

#### `POST /model-distribution`
Call count and total cost per model.

**Response:** `[{"model": "claude-sonnet-4-6", "call_count": 12000, "total_cost": 890.0}, ...]`

#### `POST /token-breakdown`
Total tokens by type across the filtered period.

**Response:** `[{"token_type": "Input", "total": 4500000}, {"token_type": "Output", "total": 1200000}, ...]`

Token types: `Input`, `Output`, `Cache Read`, `Cache Creation`.

---

### Team — `/api/v1/team`

#### `POST /by-practice`
Session count and total cost per engineering practice.

**Response:** `[{"practice": "Platform Engineering", "session_count": 980, "total_cost": 234.5}, ...]`

#### `POST /by-level`
Session count per seniority level.

**Response:** `[{"level": "L4", "session_count": 1200}, ...]`

#### `POST /by-location`
Session count per office location.

**Response:** `[{"location": "United States", "session_count": 2100}, ...]`

#### `POST /top-engineers`
Top 10 engineers by session count.

**Response:**
```json
[
  {
    "full_name": "Alice Smith",
    "practice": "ML Engineering",
    "level": "L5",
    "session_count": 87,
    "total_cost": 21.34,
    "avg_cost_per_session": 0.245,
    "preferred_model": "claude-sonnet-4-6"
  },
  ...
]
```

---

### Activity — `/api/v1/activity`

#### `POST /hourly-heatmap`
Session counts by hour of day and day of week.

**Response:** `[{"hour": 9, "day_of_week": "Monday", "session_count": 45}, ...]`

Hours are 0–23 (UTC). Days are full English names.

#### `POST /day-of-week`
Total session counts per day of week.

**Response:** `[{"day_of_week": "Monday", "session_count": 820}, ...]`

#### `POST /business-hours`
Sessions split between business hours (09:00–17:00) and after hours.

**Response:** `[{"category": "Business Hours 9-17", "session_count": 3200}, {"category": "After Hours", "session_count": 1800}]`

---

### Tools — `/api/v1/tools`

#### `POST /frequency`
Total call count per tool, descending.

**Response:** `[{"tool_name": "Read", "call_count": 45000}, ...]`

#### `POST /accept-reject`
Accept and reject counts per tool.

**Response:** `[{"tool_name": "Edit", "accept_count": 8900, "reject_count": 340}, ...]`

#### `POST /success-rate`
Fraction of tool calls that succeeded, sorted ascending (lowest first).

**Response:** `[{"tool_name": "Bash", "success_rate": 0.87}, ...]`

#### `POST /execution-time`
Average execution duration per tool in milliseconds.

**Response:** `[{"tool_name": "Bash", "avg_duration_ms": 1240.5}, ...]`

---

### Sessions — `/api/v1/sessions`

#### `POST /duration-hist`
Raw per-session duration data for histogram rendering. **Note:** binning is the caller's responsibility (app.py uses log-scale bins via numpy).

**Response:** `[{"session_id": "abc123", "duration_mins": 8.4}, ...]`

#### `POST /cost-by-practice`
Per-session cost with practice label, used for box plot distribution.

**Response:** `[{"session_id": "abc123", "practice": "Backend Engineering", "total_cost": 0.31}, ...]`

#### `POST /api-latency`
Average API call duration per model in milliseconds.

**Response:** `[{"model": "claude-sonnet-4-6", "avg_duration_ms": 2340.1}, ...]`

#### `POST /error-breakdown`
Count of API errors grouped by HTTP status code.

**Response:** `[{"status_code": "429", "count": 14}, {"status_code": "500", "count": 3}, ...]`

#### `POST /level-cost-correlation`
Average cost per session for each seniority level.

**Response:** `[{"level": "L1", "avg_cost_per_session": 0.18}, ...]`

---

### Forecast — `/api/v1/forecast`

#### `POST /summary`
Returns normalized daily cost history, a 14-day forecast, optional cross-validation metrics, and detected anomalies.

**Response:**
```json
{
  "status": "ok",
  "message": null,
  "history": [
    {"ds": "2025-12-10", "y": 1.5},
    {"ds": "2025-12-11", "y": 2.0}
  ],
  "forecast": [
    {
      "ds": "2025-12-12",
      "yhat": 2.1,
      "yhat_lower": 1.8,
      "yhat_upper": 2.4
    }
  ],
  "metrics": {
    "mae": 0.12,
    "mape": 0.08,
    "coverage": 0.91
  },
  "anomalies": [
    {
      "ds": "2025-12-11",
      "actual_cost": 2.0,
      "expected_cost": 1.2,
      "residual": 0.8
    }
  ]
}
```

`status` values:
- `ok` — forecast generated successfully
- `insufficient_data` — not enough daily history to forecast
- `forecast_error` — the forecast pipeline failed for the current data slice

Notes:
- `history` is normalized to daily cadence for the selected date range
- `forecast` contains only forward-looking rows
- `metrics` may be `null` when there is enough history to forecast but not enough for cross-validation
- `anomalies` are based on residuals between actual cost and in-sample expected cost
