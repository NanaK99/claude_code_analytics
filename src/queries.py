import datetime
from typing import List
import pandas as pd
from pydantic import BaseModel, field_validator

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

    assert f.date_start <= f.date_end, (
        f"date_start ({f.date_start}) must be <= date_end ({f.date_end})"
    )

    date_start = f.date_start.isoformat()
    date_end   = f.date_end.isoformat()
    conds = [f"{ts_col} BETWEEN '{date_start}' AND '{date_end}'"]

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
    cache_reads, total = row
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
               COUNT(DISTINCT up.session_id) AS session_count,
               COALESCE(SUM(ar.cost_usd), 0) AS total_cost
        FROM user_prompts up
        JOIN employees e ON up.user_email = e.email
        LEFT JOIN (SELECT session_id, SUM(cost_usd) AS cost_usd FROM api_requests GROUP BY 1) ar
            ON up.session_id = ar.session_id
        {w}
        GROUP BY e.full_name, e.practice, e.level
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


def get_tool_execution_time(conn, filters: dict) -> pd.DataFrame:
    w = _where(filters, "tr.timestamp")
    return _df(conn, f"""
        SELECT tool_name, AVG(duration_ms) AS avg_duration_ms
        FROM tool_results tr JOIN employees e ON tr.user_email = e.email {w}
        GROUP BY tool_name ORDER BY avg_duration_ms DESC
    """)
