import datetime
from typing import List
import pandas as pd
from pydantic import BaseModel, field_validator, model_validator

_VALID_PRACTICES = {
    "Platform Engineering", "Data Engineering", "ML Engineering",
    "Backend Engineering", "Frontend Engineering",
}
_VALID_LEVELS    = {f"L{i}" for i in range(1, 11)}
_VALID_LOCATIONS = {"United States", "Germany", "United Kingdom", "Poland", "Canada"}


class Filters(BaseModel):
    date_start: datetime.date
    date_end:   datetime.date
    practices:  List[str] = []
    levels:     List[str] = []
    locations:  List[str] = []

    @model_validator(mode="after")
    def check_date_order(self) -> "Filters":
        if self.date_start > self.date_end:
            raise ValueError(
                f"date_start ({self.date_start}) must be <= date_end ({self.date_end})"
            )
        return self

    @field_validator("practices", mode="before")
    @classmethod
    def validate_practices(cls, values: list) -> list:
        for v in values:
            if v not in _VALID_PRACTICES:
                raise ValueError(f"Invalid practice: {v!r}")
        return values

    @field_validator("levels", mode="before")
    @classmethod
    def validate_levels(cls, values: list) -> list:
        for v in values:
            if v not in _VALID_LEVELS:
                raise ValueError(f"Invalid level: {v!r}")
        return values

    @field_validator("locations", mode="before")
    @classmethod
    def validate_locations(cls, values: list) -> list:
        for v in values:
            if v not in _VALID_LOCATIONS:
                raise ValueError(f"Invalid location: {v!r}")
        return values


def _where(filters: dict, ts_col: str) -> str:
    """Build a SQL WHERE clause. Assumes `employees e` is already joined."""
    f = Filters(**filters)

    date_start = f.date_start.isoformat()
    date_end   = f.date_end.isoformat()
    conds = [f"CAST({ts_col} AS DATE) BETWEEN '{date_start}' AND '{date_end}'"]

    if f.practices:
        vals = ", ".join(f"'{p}'" for p in f.practices)
        conds.append(f"e.practice IN ({vals})")

    if f.levels:
        vals = ", ".join(f"'{lv}'" for lv in f.levels)
        conds.append(f"e.level IN ({vals})")

    if f.locations:
        vals = ", ".join(f"'{loc}'" for loc in f.locations)
        conds.append(f"e.location IN ({vals})")

    return "WHERE " + " AND ".join(conds)


def _df(conn, sql: str) -> pd.DataFrame:
    return conn.execute(sql).df()


# ── Overview ──────────────────────────────────────────────────────────────────

def get_kpi_metrics(conn, filters: dict) -> dict:
    # Query api_requests for sessions, engineers, cost, and request count
    w_req = _where(filters, "ar.timestamp")
    row = conn.execute(f"""
        SELECT
            COUNT(DISTINCT ar.session_id) AS total_sessions,
            COUNT(DISTINCT ar.user_email) AS active_engineers,
            COALESCE(SUM(ar.cost_usd), 0) AS total_cost,
            COUNT(*)                       AS total_requests
        FROM api_requests ar
        JOIN employees e ON ar.user_email = e.email
        {w_req}
    """).fetchone()
    total_sessions, active_engineers, total_cost, total_requests = row

    # Query api_errors separately to avoid JOIN fan-out (many api_requests × many api_errors)
    w_err = _where(filters, "ae.timestamp")
    total_errors = conn.execute(f"""
        SELECT COUNT(*)
        FROM api_errors ae
        JOIN employees e ON ae.user_email = e.email
        {w_err}
    """).fetchone()[0]

    error_rate = (total_errors / total_requests) if total_requests else 0.0
    return {
        "total_sessions":   int(total_sessions or 0),
        "active_engineers": int(active_engineers or 0),
        "total_cost":       float(total_cost or 0),
        "error_rate":       error_rate,
    }


def get_daily_sessions(conn, filters: dict) -> pd.DataFrame:
    w = _where(filters, "up.timestamp")
    return _df(conn, f"""
        SELECT CAST(up.timestamp AS DATE) AS date, COUNT(DISTINCT up.session_id) AS session_count
        FROM user_prompts up
        JOIN employees e ON up.user_email = e.email
        {w}
        GROUP BY 1 ORDER BY 1
    """)


def get_session_kpis(conn, filters: dict) -> dict:
    # avg_duration_mins from api_requests (multiple rows per session give non-zero spreads)
    w_ar = _where(filters, "ar.timestamp")
    dur_row = conn.execute(f"""
        SELECT AVG(session_dur)
        FROM (
            SELECT ar.session_id,
                   EXTRACT(epoch FROM (MAX(ar.timestamp) - MIN(ar.timestamp))) / 60.0 AS session_dur
            FROM api_requests ar JOIN employees e ON ar.user_email = e.email
            {w_ar}
            GROUP BY ar.session_id
        ) sub
    """).fetchone()

    # avg_prompts_per_session from user_prompts
    w_up = _where(filters, "up.timestamp")
    prompts_row = conn.execute(f"""
        SELECT COUNT(*) * 1.0 / NULLIF(COUNT(DISTINCT session_id), 0)
        FROM user_prompts up JOIN employees e ON up.user_email = e.email
        {w_up}
    """).fetchone()

    return {
        "avg_duration_mins":      float(dur_row[0] or 0),
        "avg_prompts_per_session": float(prompts_row[0] or 0),
    }


# Pricing: claude-sonnet-4-6 input = $3.00/MTok, cache_read = $0.30/MTok
# Applied uniformly across all models as a stated approximation.
_CACHE_SAVINGS_PER_TOKEN = (3.00 - 0.30) / 1_000_000  # $2.70 per MTok


def get_cache_savings(conn, filters: dict) -> float:
    w = _where(filters, "ar.timestamp")
    row = conn.execute(f"""
        SELECT COALESCE(SUM(cache_read_tokens), 0)
        FROM api_requests ar JOIN employees e ON ar.user_email = e.email {w}
    """).fetchone()
    return float(row[0] or 0) * _CACHE_SAVINGS_PER_TOKEN


# ── Cost & Tokens ─────────────────────────────────────────────────────────────

def get_cost_by_practice_over_time(conn, filters: dict) -> pd.DataFrame:
    w = _where(filters, "ar.timestamp")
    return _df(conn, f"""
        SELECT CAST(ar.timestamp AS DATE) AS date, e.practice, SUM(ar.cost_usd) AS total_cost
        FROM api_requests ar JOIN employees e ON ar.user_email = e.email {w}
        GROUP BY 1, 2 ORDER BY 1, 2
    """)


def get_cost_by_level_over_time(conn, filters: dict) -> pd.DataFrame:
    w = _where(filters, "ar.timestamp")
    return _df(conn, f"""
        SELECT CAST(ar.timestamp AS DATE) AS date, e.level, SUM(ar.cost_usd) AS total_cost
        FROM api_requests ar JOIN employees e ON ar.user_email = e.email {w}
        GROUP BY 1, 2 ORDER BY 1, 2
    """)


def get_token_breakdown(conn, filters: dict) -> pd.DataFrame:
    w = _where(filters, "ar.timestamp")
    row = conn.execute(f"""
        SELECT COALESCE(SUM(input_tokens), 0),
               COALESCE(SUM(output_tokens), 0),
               COALESCE(SUM(cache_read_tokens), 0),
               COALESCE(SUM(cache_creation_tokens), 0)
        FROM api_requests ar JOIN employees e ON ar.user_email = e.email {w}
    """).fetchone()
    return pd.DataFrame({
        "token_type": ["Input", "Output", "Cache Read", "Cache Creation"],
        "total": list(row),
    })


def get_avg_cost_per_session_over_time(conn, filters: dict) -> pd.DataFrame:
    w = _where(filters, "up.timestamp")
    return _df(conn, f"""
        WITH sc AS (
            SELECT session_id, SUM(cost_usd) AS total_cost
            FROM api_requests GROUP BY session_id
        )
        SELECT CAST(up.timestamp AS DATE) AS date,
               SUM(COALESCE(sc.total_cost, 0)) / COUNT(DISTINCT up.session_id) AS avg_cost_per_session
        FROM user_prompts up
        JOIN employees e ON up.user_email = e.email
        LEFT JOIN sc ON up.session_id = sc.session_id
        {w}
        GROUP BY 1 ORDER BY 1
    """)


def get_daily_cost_totals(conn, filters: dict) -> pd.DataFrame:
    w = _where(filters, "ar.timestamp")
    return _df(conn, f"""
        SELECT CAST(ar.timestamp AS DATE) AS ds, COALESCE(SUM(ar.cost_usd), 0) AS y
        FROM api_requests ar JOIN employees e ON ar.user_email = e.email {w}
        GROUP BY 1 ORDER BY 1
    """)


def get_model_distribution(conn, filters: dict) -> pd.DataFrame:
    w = _where(filters, "ar.timestamp")
    return _df(conn, f"""
        SELECT model, COUNT(*) AS call_count, SUM(cost_usd) AS total_cost
        FROM api_requests ar JOIN employees e ON ar.user_email = e.email {w}
        GROUP BY model ORDER BY call_count DESC
    """)


def get_cache_hit_rate(conn, filters: dict) -> float:
    w = _where(filters, "ar.timestamp")
    row = conn.execute(f"""
        SELECT SUM(cache_read_tokens),
               SUM(input_tokens + cache_read_tokens + cache_creation_tokens)
        FROM api_requests ar JOIN employees e ON ar.user_email = e.email {w}
    """).fetchone()
    cache_reads = row[0] or 0
    total       = row[1] or 0
    return float(cache_reads) / float(total) if total else 0.0


# ── Team & Engineers ──────────────────────────────────────────────────────────

def get_usage_by_practice(conn, filters: dict) -> pd.DataFrame:
    w = _where(filters, "up.timestamp")
    return _df(conn, f"""
        SELECT e.practice, COUNT(DISTINCT up.session_id) AS session_count,
               COALESCE(SUM(ar.cost_usd), 0) AS total_cost
        FROM user_prompts up
        JOIN employees e ON up.user_email = e.email
        LEFT JOIN (SELECT session_id, SUM(cost_usd) AS cost_usd FROM api_requests GROUP BY 1) ar
            ON up.session_id = ar.session_id
        {w}
        GROUP BY e.practice ORDER BY session_count DESC
    """)


def get_usage_by_level(conn, filters: dict) -> pd.DataFrame:
    w = _where(filters, "up.timestamp")
    return _df(conn, f"""
        SELECT e.level, COUNT(DISTINCT up.session_id) AS session_count
        FROM user_prompts up JOIN employees e ON up.user_email = e.email {w}
        GROUP BY e.level ORDER BY e.level
    """)


def get_top_engineers(conn, filters: dict) -> pd.DataFrame:
    w = _where(filters, "up.timestamp")
    return _df(conn, f"""
        SELECT e.full_name, e.practice, e.level,
               COUNT(DISTINCT up.session_id)                                          AS session_count,
               COALESCE(SUM(ar.cost_usd), 0)                                         AS total_cost,
               COALESCE(SUM(ar.cost_usd), 0)
                   / NULLIF(COUNT(DISTINCT up.session_id), 0)                         AS avg_cost_per_session,
               (
                   SELECT model FROM api_requests inner_ar
                   WHERE inner_ar.user_email = e.email
                   GROUP BY model ORDER BY COUNT(*) DESC LIMIT 1
               )                                                                      AS preferred_model
        FROM user_prompts up
        JOIN employees e ON up.user_email = e.email
        LEFT JOIN (
            SELECT session_id, SUM(cost_usd) AS cost_usd
            FROM api_requests GROUP BY 1
        ) ar ON up.session_id = ar.session_id
        {w}
        GROUP BY e.full_name, e.practice, e.level, e.email
        ORDER BY session_count DESC LIMIT 10
    """)


def get_usage_by_location(conn, filters: dict) -> pd.DataFrame:
    w = _where(filters, "up.timestamp")
    return _df(conn, f"""
        SELECT e.location, COUNT(DISTINCT up.session_id) AS session_count
        FROM user_prompts up JOIN employees e ON up.user_email = e.email {w}
        GROUP BY e.location ORDER BY session_count DESC
    """)


# ── Activity Patterns ─────────────────────────────────────────────────────────

def get_hourly_heatmap(conn, filters: dict) -> pd.DataFrame:
    w = _where(filters, "up.timestamp")
    return _df(conn, f"""
        SELECT EXTRACT(hour FROM up.timestamp) AS hour,
               DAYNAME(up.timestamp)           AS day_of_week,
               COUNT(DISTINCT up.session_id)   AS session_count
        FROM user_prompts up JOIN employees e ON up.user_email = e.email {w}
        GROUP BY 1, 2
    """)


def get_day_of_week_counts(conn, filters: dict) -> pd.DataFrame:
    w = _where(filters, "up.timestamp")
    return _df(conn, f"""
        SELECT DAYNAME(up.timestamp) AS day_of_week,
               COUNT(DISTINCT up.session_id) AS session_count
        FROM user_prompts up JOIN employees e ON up.user_email = e.email {w}
        GROUP BY 1
    """)


def get_business_hours_split(conn, filters: dict) -> pd.DataFrame:
    w = _where(filters, "up.timestamp")
    return _df(conn, f"""
        SELECT
            CASE WHEN EXTRACT(hour FROM up.timestamp) BETWEEN 9 AND 17
                 THEN 'Business Hours (9–17)'
                 ELSE 'After Hours'
            END AS category,
            COUNT(DISTINCT up.session_id) AS session_count
        FROM user_prompts up JOIN employees e ON up.user_email = e.email {w}
        GROUP BY 1
    """)


# ── Tool Behavior ─────────────────────────────────────────────────────────────

def get_tool_frequency(conn, filters: dict) -> pd.DataFrame:
    w = _where(filters, "td.timestamp")
    return _df(conn, f"""
        SELECT tool_name, COUNT(*) AS call_count
        FROM tool_decisions td JOIN employees e ON td.user_email = e.email {w}
        GROUP BY tool_name ORDER BY call_count DESC
    """)


def get_tool_accept_reject(conn, filters: dict) -> pd.DataFrame:
    w = _where(filters, "td.timestamp")
    return _df(conn, f"""
        SELECT tool_name,
               COUNT(*) FILTER (WHERE decision = 'accept') AS accept_count,
               COUNT(*) FILTER (WHERE decision = 'reject') AS reject_count
        FROM tool_decisions td JOIN employees e ON td.user_email = e.email {w}
        GROUP BY tool_name ORDER BY (accept_count + reject_count) DESC
    """)


def get_tool_success_rate(conn, filters: dict) -> pd.DataFrame:
    w = _where(filters, "tr.timestamp")
    return _df(conn, f"""
        SELECT tool_name, AVG(success::INT) AS success_rate
        FROM tool_results tr JOIN employees e ON tr.user_email = e.email {w}
        GROUP BY tool_name ORDER BY success_rate ASC
    """)


def get_tool_execution_time(conn, filters: dict) -> pd.DataFrame:
    w = _where(filters, "tr.timestamp")
    return _df(conn, f"""
        SELECT tool_name, AVG(duration_ms) AS avg_duration_ms
        FROM tool_results tr JOIN employees e ON tr.user_email = e.email {w}
        GROUP BY tool_name ORDER BY avg_duration_ms DESC
    """)


# ── Session Intelligence ───────────────────────────────────────────────────

def get_session_duration_hist(conn, filters: dict) -> pd.DataFrame:
    w = _where(filters, "ar.timestamp")
    return _df(conn, f"""
        SELECT ar.session_id,
               EXTRACT(epoch FROM (MAX(ar.timestamp) - MIN(ar.timestamp))) / 60.0 AS duration_mins
        FROM api_requests ar JOIN employees e ON ar.user_email = e.email
        {w}
        GROUP BY ar.session_id
    """)


def get_session_cost_by_practice(conn, filters: dict) -> pd.DataFrame:
    w = _where(filters, "up.timestamp")
    return _df(conn, f"""
        WITH sc AS (
            SELECT session_id, SUM(cost_usd) AS total_cost
            FROM api_requests GROUP BY session_id
        )
        SELECT up.session_id, e.practice, COALESCE(sc.total_cost, 0) AS total_cost
        FROM user_prompts up
        JOIN employees e ON up.user_email = e.email
        LEFT JOIN sc ON up.session_id = sc.session_id
        {w}
    """)


def get_api_latency_by_model(conn, filters: dict) -> pd.DataFrame:
    w = _where(filters, "ar.timestamp")
    return _df(conn, f"""
        SELECT model, AVG(duration_ms) AS avg_duration_ms
        FROM api_requests ar JOIN employees e ON ar.user_email = e.email {w}
        GROUP BY model ORDER BY avg_duration_ms DESC
    """)


def get_error_breakdown(conn, filters: dict) -> pd.DataFrame:
    w = _where(filters, "ae.timestamp")
    return _df(conn, f"""
        SELECT CASE WHEN status_code = 'undefined' THEN 'Unknown' ELSE status_code END AS status_code,
               COUNT(*) AS count
        FROM api_errors ae JOIN employees e ON ae.user_email = e.email {w}
        GROUP BY 1 ORDER BY count DESC
    """)


def get_level_cost_correlation(conn, filters: dict) -> pd.DataFrame:
    w = _where(filters, "up.timestamp")
    return _df(conn, f"""
        WITH sc AS (
            SELECT session_id, SUM(cost_usd) AS total_cost
            FROM api_requests GROUP BY session_id
        )
        SELECT e.level,
               SUM(COALESCE(sc.total_cost, 0)) / COUNT(DISTINCT up.session_id) AS avg_cost_per_session
        FROM user_prompts up
        JOIN employees e ON up.user_email = e.email
        LEFT JOIN sc ON up.session_id = sc.session_id
        {w}
        GROUP BY e.level ORDER BY e.level
    """)
