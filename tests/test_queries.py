import duckdb
import pytest
import pandas as pd
from pydantic import ValidationError
from src.schema import init_db
from src.queries import (
    get_kpi_metrics, get_daily_sessions,
    get_cost_by_practice_over_time, get_cost_by_level_over_time,
    get_token_breakdown, get_model_distribution, get_cache_hit_rate,
    get_usage_by_practice, get_usage_by_level, get_top_engineers, get_usage_by_location,
    get_hourly_heatmap, get_day_of_week_counts, get_business_hours_split,
    get_tool_frequency, get_tool_accept_reject, get_tool_execution_time,
)


@pytest.fixture
def conn():
    c = duckdb.connect(":memory:")
    init_db(c)
    c.execute("INSERT INTO employees VALUES ('alice@example.com','Alice','Backend Engineering','L5','Germany')")
    c.execute("INSERT INTO employees VALUES ('bob@example.com','Bob','Frontend Engineering','L3','Poland')")
    c.execute("""INSERT INTO api_requests VALUES
        ('s1','alice@example.com','2025-12-10 10:00:00','claude-sonnet-4-6',100,200,500,0,0.01,9000,'vscode'),
        ('s1','alice@example.com','2025-12-10 10:05:00','claude-haiku-4-5-20251001',50,100,0,0,0.001,2000,'vscode'),
        ('s2','bob@example.com','2025-12-11 20:00:00','claude-opus-4-6',0,300,1000,0,0.05,15000,'iTerm2')
    """)
    c.execute("""INSERT INTO user_prompts VALUES
        ('s1','alice@example.com','2025-12-10 10:00:00',300,'vscode'),
        ('s2','bob@example.com','2025-12-11 20:00:00',500,'iTerm2')
    """)
    c.execute("""INSERT INTO tool_decisions VALUES
        ('s1','alice@example.com','2025-12-10 10:06:00','Read','accept','config','vscode'),
        ('s1','alice@example.com','2025-12-10 10:07:00','Edit','reject','user_reject','vscode'),
        ('s2','bob@example.com','2025-12-11 20:01:00','Read','accept','config','iTerm2')
    """)
    c.execute("""INSERT INTO tool_results VALUES
        ('s1','alice@example.com','2025-12-10 10:06:10','Read','accept','config',true,61,2048,'vscode'),
        ('s2','bob@example.com','2025-12-11 20:01:05','Read','accept','config',true,120,NULL,'iTerm2')
    """)
    c.execute("""INSERT INTO api_errors VALUES
        ('s2','bob@example.com','2025-12-11 20:00:30','claude-opus-4-6','Token expired','401',1,500,'iTerm2')
    """)
    return c


ALL_FILTERS = {
    "date_start": "2025-12-01",
    "date_end": "2026-02-28",
    "practices": [],
    "levels": [],
    "locations": [],
}


def test_get_kpi_metrics(conn):
    result = get_kpi_metrics(conn, ALL_FILTERS)
    assert result["total_sessions"] == 2
    assert result["active_engineers"] == 2
    assert result["total_cost"] == pytest.approx(0.061, rel=1e-2)
    # 1 api_error / 3 api_requests = ~33.3%
    # A wrong JOIN-based implementation would return 3/3=100% — this assertion catches it
    assert result["error_rate"] == pytest.approx(1 / 3, rel=1e-2)


def test_get_daily_sessions_returns_dataframe(conn):
    df = get_daily_sessions(conn, ALL_FILTERS)
    assert isinstance(df, pd.DataFrame)
    assert set(df.columns) >= {"date", "session_count"}
    assert len(df) > 0


def test_get_usage_by_practice(conn):
    df = get_usage_by_practice(conn, ALL_FILTERS)
    assert "practice" in df.columns
    assert "session_count" in df.columns
    assert set(df["practice"]) <= {"Backend Engineering", "Frontend Engineering"}


def test_get_top_engineers_limit_10(conn):
    df = get_top_engineers(conn, ALL_FILTERS)
    assert "full_name" in df.columns
    assert len(df) <= 10


def test_get_top_engineers(conn):
    df = get_top_engineers(conn, ALL_FILTERS)
    assert not df.empty
    assert "avg_cost_per_session" in df.columns
    assert "preferred_model" in df.columns
    # alice (s1, cost=0.011, 1 session) → avg_cost_per_session ≈ 0.011
    alice_row = df[df["full_name"] == "Alice"].iloc[0]
    assert alice_row["avg_cost_per_session"] == pytest.approx(0.011, rel=1e-3)
    assert alice_row["preferred_model"] in {"claude-sonnet-4-6", "claude-haiku-4-5-20251001"}


def test_get_hourly_heatmap(conn):
    df = get_hourly_heatmap(conn, ALL_FILTERS)
    assert set(df.columns) >= {"hour", "day_of_week", "session_count"}


def test_get_tool_frequency(conn):
    df = get_tool_frequency(conn, ALL_FILTERS)
    assert "tool_name" in df.columns
    assert "call_count" in df.columns
    # 3 tool_decision rows for Read (2) + Edit (1); Read should be top
    read_count = df.loc[df["tool_name"] == "Read", "call_count"].values[0]
    assert read_count == 2


def test_get_tool_accept_reject(conn):
    df = get_tool_accept_reject(conn, ALL_FILTERS)
    assert set(df.columns) >= {"tool_name", "accept_count", "reject_count"}
    edit_row = df[df["tool_name"] == "Edit"]
    assert edit_row["reject_count"].values[0] == 1


def test_filters_by_practice(conn):
    filters = {**ALL_FILTERS, "practices": ["Backend Engineering"]}
    df = get_usage_by_practice(conn, filters)
    assert all(p == "Backend Engineering" for p in df["practice"])


def test_empty_result_when_no_matching_location(conn):
    filters = {**ALL_FILTERS, "locations": ["Canada"]}
    result = get_kpi_metrics(conn, filters)
    assert result["total_sessions"] == 0


def test_get_cost_by_practice_over_time(conn):
    df = get_cost_by_practice_over_time(conn, ALL_FILTERS)
    assert isinstance(df, pd.DataFrame)
    assert set(df.columns) >= {"date", "practice", "total_cost"}
    assert len(df) > 0


def test_get_cost_by_level_over_time(conn):
    df = get_cost_by_level_over_time(conn, ALL_FILTERS)
    assert isinstance(df, pd.DataFrame)
    assert set(df.columns) >= {"date", "level", "total_cost"}
    assert len(df) > 0


def test_get_token_breakdown(conn):
    df = get_token_breakdown(conn, ALL_FILTERS)
    assert list(df["token_type"]) == ["Input", "Output", "Cache Read", "Cache Creation"]
    assert df["total"].notna().all()
    # alice: input=100+50=150, output=200+100=300; bob: input=0, output=300
    assert df.loc[df["token_type"] == "Input", "total"].values[0] == 150


def test_get_token_breakdown_empty(conn):
    # No data for this location — should return zeros, not NULLs
    filters = {**ALL_FILTERS, "locations": ["Canada"]}
    df = get_token_breakdown(conn, filters)
    assert df["total"].notna().all()
    assert (df["total"] == 0).all()


def test_get_model_distribution(conn):
    df = get_model_distribution(conn, ALL_FILTERS)
    assert set(df.columns) >= {"model", "call_count", "total_cost"}
    assert set(df["model"]) == {"claude-sonnet-4-6", "claude-haiku-4-5-20251001", "claude-opus-4-6"}


def test_get_cache_hit_rate(conn):
    # cache_read_tokens: 500 (alice row 1) + 1000 (bob)
    # total denominator: (100+500+0) + (50+0+0) + (0+1000+0) = 600+50+1000 = 1650
    rate = get_cache_hit_rate(conn, ALL_FILTERS)
    assert isinstance(rate, float)
    assert rate == pytest.approx(1500 / 1650, rel=1e-3)


def test_get_cache_hit_rate_empty(conn):
    filters = {**ALL_FILTERS, "locations": ["Canada"]}
    rate = get_cache_hit_rate(conn, filters)
    assert rate == 0.0


def test_get_usage_by_level(conn):
    df = get_usage_by_level(conn, ALL_FILTERS)
    assert set(df.columns) >= {"level", "session_count"}
    assert set(df["level"]) <= {"L5", "L3"}


def test_get_usage_by_location(conn):
    df = get_usage_by_location(conn, ALL_FILTERS)
    assert set(df.columns) >= {"location", "session_count"}
    assert set(df["location"]) <= {"Germany", "Poland"}


def test_get_day_of_week_counts(conn):
    df = get_day_of_week_counts(conn, ALL_FILTERS)
    assert set(df.columns) >= {"day_of_week", "session_count"}
    assert len(df) > 0


def test_get_business_hours_split(conn):
    df = get_business_hours_split(conn, ALL_FILTERS)
    assert "category" in df.columns
    assert "session_count" in df.columns
    # bob's session is at hour 20 (after hours), alice's is at hour 10 (business hours)
    biz = df.loc[df["category"] == "Business Hours (9\u201317)", "session_count"].values[0]
    after = df.loc[df["category"] == "After Hours", "session_count"].values[0]
    assert biz == 1
    assert after == 1


def test_get_tool_execution_time(conn):
    df = get_tool_execution_time(conn, ALL_FILTERS)
    assert set(df.columns) >= {"tool_name", "avg_duration_ms"}
    read_avg = df.loc[df["tool_name"] == "Read", "avg_duration_ms"].values[0]
    # tool_results: Read row 1 = 61ms, Read row 2 = 120ms → avg = 90.5ms
    assert read_avg == pytest.approx(90.5, rel=1e-3)


# ── _where() validation tests ──────────────────────────────────────────────
from src.queries import _where

def _base_filters():
    return {
        "date_start": "2025-12-01",
        "date_end":   "2026-02-28",
        "practices":  [],
        "levels":     [],
        "locations":  [],
    }

def test_where_invalid_practice_raises():
    f = _base_filters()
    f["practices"] = ["Hacking Division"]
    with pytest.raises(ValueError, match="Invalid practice"):
        _where(f, "up.timestamp")

def test_where_invalid_level_raises():
    f = _base_filters()
    f["levels"] = ["L99"]
    with pytest.raises(ValueError, match="Invalid level"):
        _where(f, "up.timestamp")

def test_where_invalid_location_raises():
    f = _base_filters()
    f["locations"] = ["Mars"]
    with pytest.raises(ValueError, match="Invalid location"):
        _where(f, "up.timestamp")

def test_where_invalid_date_format_raises():
    f = _base_filters()
    f["date_start"] = "not-a-date"
    with pytest.raises(ValueError):
        _where(f, "up.timestamp")

def test_where_date_start_after_date_end_raises():
    f = _base_filters()
    f["date_start"] = "2026-02-28"
    f["date_end"]   = "2025-12-01"
    with pytest.raises(ValidationError):
        _where(f, "up.timestamp")
