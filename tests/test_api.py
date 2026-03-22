import os
import unittest.mock as mock
import duckdb
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.schema import init_db

API_KEY = "test-key"
HEADERS = {"X-API-Key": API_KEY}
VALID_FILTERS = {
    "date_start": "2025-12-01",
    "date_end": "2026-02-28",
    "practices": [],
    "levels": [],
    "locations": [],
}


@pytest.fixture(scope="module")
def seed_db():
    """In-memory DuckDB seeded with minimal rows for all 6 tables."""
    c = duckdb.connect(":memory:")
    init_db(c)
    c.execute("INSERT INTO employees VALUES ('alice@example.com','Alice','Backend Engineering','L5','Germany')")
    c.execute("INSERT INTO employees VALUES ('bob@example.com','Bob','ML Engineering','L3','Poland')")
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


@pytest.fixture
def client(seed_db, monkeypatch):
    """
    Test client per-test (function scope) so monkeypatch cleans up env vars automatically.

    Strategy:
    - monkeypatch.setenv sets API_KEY without leaking to other test modules
    - app.dependency_overrides[get_db] injects seed_db so routers never touch the real DB
    - mock.patch("src.api.main.Path") prevents the lifespan from raising on missing DB file
    - mock.patch("src.api.main.duckdb") prevents the lifespan from opening the real DB file
      (patched only in src.api.main namespace — does NOT affect query functions)
    """
    monkeypatch.setenv("API_KEY", API_KEY)

    from src.api.main import app
    from src.api.deps import get_db

    app.dependency_overrides[get_db] = lambda: seed_db

    with (
        mock.patch("src.api.main.Path") as mock_path,
        mock.patch("src.api.main.duckdb") as mock_duckdb,
    ):
        mock_path.return_value.exists.return_value = True
        # Do NOT set connect.return_value = seed_db — lifespan would then call
        # seed_db.close() on teardown, invalidating the module-scoped connection.
        # The get_db dependency override already injects seed_db for all routers.
        with TestClient(app) as c:
            yield c

    app.dependency_overrides.clear()


# ── Auth tests ────────────────────────────────────────────────────────────────

def test_missing_api_key_returns_403(client):
    resp = client.post("/api/v1/overview/kpi-metrics", json=VALID_FILTERS)
    assert resp.status_code == 403


def test_wrong_api_key_returns_403(client):
    resp = client.post(
        "/api/v1/overview/kpi-metrics",
        json=VALID_FILTERS,
        headers={"X-API-Key": "wrong-key"},
    )
    assert resp.status_code == 403


# ── Overview router ───────────────────────────────────────────────────────────

def test_overview_kpi_metrics(client):
    resp = client.post("/api/v1/overview/kpi-metrics", json=VALID_FILTERS, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_sessions"] == 2
    assert data["active_engineers"] == 2
    assert "total_cost" in data
    assert "error_rate" in data


def test_overview_daily_sessions(client):
    resp = client.post("/api/v1/overview/daily-sessions", json=VALID_FILTERS, headers=HEADERS)
    assert resp.status_code == 200
    rows = resp.json()
    assert isinstance(rows, list)
    assert all("date" in r and "session_count" in r for r in rows)


def test_overview_cache_savings_wraps_float(client):
    """get_cache_savings returns a raw float; endpoint must wrap it in CacheSavingsResponse."""
    resp = client.post("/api/v1/overview/cache-savings", json=VALID_FILTERS, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert "cache_savings_usd" in data
    assert isinstance(data["cache_savings_usd"], float)


def test_overview_session_kpis_wraps_dict(client):
    """get_session_kpis returns a dict; endpoint must match SessionKpisResponse schema."""
    resp = client.post("/api/v1/overview/session-kpis", json=VALID_FILTERS, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert "avg_duration_mins" in data
    assert "avg_prompts_per_session" in data


def test_invalid_filter_returns_422(client):
    bad = {**VALID_FILTERS, "practices": ["Nonexistent Practice"]}
    resp = client.post("/api/v1/overview/kpi-metrics", json=bad, headers=HEADERS)
    assert resp.status_code == 422


def test_invalid_date_range_returns_422(client):
    bad = {**VALID_FILTERS, "date_start": "2026-01-01", "date_end": "2025-01-01"}
    resp = client.post("/api/v1/overview/kpi-metrics", json=bad, headers=HEADERS)
    assert resp.status_code == 422


# ── Costs router ──────────────────────────────────────────────────────────────

def test_costs_by_practice(client):
    resp = client.post("/api/v1/costs/by-practice", json=VALID_FILTERS, headers=HEADERS)
    assert resp.status_code == 200
    rows = resp.json()
    assert isinstance(rows, list)
    assert all("date" in r and "practice" in r and "total_cost" in r for r in rows)


def test_costs_cache_hit_rate_wraps_float(client):
    """get_cache_hit_rate returns a raw float; endpoint must wrap it in CacheHitRateResponse."""
    resp = client.post("/api/v1/costs/cache-hit-rate", json=VALID_FILTERS, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert "cache_hit_rate" in data
    assert 0.0 <= data["cache_hit_rate"] <= 1.0


# ── Forecast router ──────────────────────────────────────────────────────────

def test_forecast_summary_happy_path_shape(client, monkeypatch):
    daily_costs = pd.DataFrame(
        {
            "ds": pd.to_datetime(["2025-12-10", "2025-12-11"]),
            "y": [1.5, 2.0],
        }
    )
    expected_filters = {
        **VALID_FILTERS,
        "date_start": pd.Timestamp(VALID_FILTERS["date_start"]).date(),
        "date_end": pd.Timestamp(VALID_FILTERS["date_end"]).date(),
    }
    expected_summary = {
        "status": "ok",
        "message": None,
        "history": [{"ds": "2025-12-10", "y": 1.5}, {"ds": "2025-12-11", "y": 2.0}],
        "forecast": [
            {
                "ds": "2025-12-12",
                "yhat": 2.1,
                "yhat_lower": 1.8,
                "yhat_upper": 2.4,
            }
        ],
        "metrics": {"mae": 0.1, "mape": 0.05, "coverage": 0.9},
        "anomalies": [
            {
                "ds": "2025-12-11",
                "actual_cost": 2.0,
                "expected_cost": 1.2,
                "residual": 0.8,
            }
        ],
    }

    monkeypatch.setattr(
        "src.api.routers.forecast.get_daily_cost_totals",
        lambda db, filters: daily_costs,
    )
    def build_summary(df, periods=14, filters=None):
        assert df.equals(daily_costs)
        assert periods == 14
        assert filters == expected_filters
        return expected_summary

    monkeypatch.setattr("src.api.routers.forecast.build_forecast_summary", build_summary)

    resp = client.post("/api/v1/forecast/summary", json=VALID_FILTERS, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "history" in data and isinstance(data["history"], list)
    assert "forecast" in data and isinstance(data["forecast"], list)
    assert "metrics" in data
    assert "anomalies" in data and isinstance(data["anomalies"], list)


def test_forecast_summary_insufficient_data_shape(client, monkeypatch):
    daily_costs = pd.DataFrame(
        {
            "ds": pd.to_datetime(["2025-12-10"]),
            "y": [1.5],
        }
    )
    expected_filters = {
        **VALID_FILTERS,
        "date_start": pd.Timestamp(VALID_FILTERS["date_start"]).date(),
        "date_end": pd.Timestamp(VALID_FILTERS["date_end"]).date(),
    }
    expected_summary = {
        "status": "insufficient_data",
        "message": "At least 14 days of daily cost history are required for forecasting.",
        "history": [{"ds": "2025-12-10", "y": 1.5}],
        "forecast": [],
        "metrics": None,
        "anomalies": [],
    }

    monkeypatch.setattr(
        "src.api.routers.forecast.get_daily_cost_totals",
        lambda db, filters: daily_costs,
    )
    def build_summary(df, periods=14, filters=None):
        assert df.equals(daily_costs)
        assert periods == 14
        assert filters == expected_filters
        return expected_summary

    monkeypatch.setattr("src.api.routers.forecast.build_forecast_summary", build_summary)

    resp = client.post("/api/v1/forecast/summary", json=VALID_FILTERS, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "insufficient_data"
    assert isinstance(data["history"], list)
    assert data["forecast"] == []
    assert data["metrics"] is None
    assert data["anomalies"] == []


def test_forecast_summary_error_shape(client, monkeypatch):
    daily_costs = pd.DataFrame(
        {
            "ds": pd.to_datetime(["2025-12-10", "2025-12-11"]),
            "y": [1.5, 2.0],
        }
    )

    monkeypatch.setattr(
        "src.api.routers.forecast.get_daily_cost_totals",
        lambda db, filters: daily_costs,
    )
    monkeypatch.setattr(
        "src.forecasting.fit_prophet_and_predict",
        lambda history, periods=14: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    resp = client.post("/api/v1/forecast/summary", json=VALID_FILTERS, headers=HEADERS)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "forecast_error"
    assert data["message"] == "Forecasting failed: boom"
    assert data["forecast"] == []
    assert data["metrics"] is None
    assert data["anomalies"] == []
    assert len(data["history"]) == 90


def test_forecast_summary_requires_api_key(client):
    resp = client.post("/api/v1/forecast/summary", json=VALID_FILTERS)
    assert resp.status_code == 403


# ── Team router ───────────────────────────────────────────────────────────────

def test_team_by_practice(client):
    resp = client.post("/api/v1/team/by-practice", json=VALID_FILTERS, headers=HEADERS)
    assert resp.status_code == 200
    rows = resp.json()
    assert isinstance(rows, list)
    assert all("practice" in r and "session_count" in r and "total_cost" in r for r in rows)


def test_team_top_engineers(client):
    resp = client.post("/api/v1/team/top-engineers", json=VALID_FILTERS, headers=HEADERS)
    assert resp.status_code == 200
    rows = resp.json()
    assert isinstance(rows, list)
    assert len(rows) <= 10
    assert all("full_name" in r and "session_count" in r for r in rows)


# ── Activity router ───────────────────────────────────────────────────────────

def test_activity_hourly_heatmap(client):
    resp = client.post("/api/v1/activity/hourly-heatmap", json=VALID_FILTERS, headers=HEADERS)
    assert resp.status_code == 200
    rows = resp.json()
    assert isinstance(rows, list)
    assert all("hour" in r and "day_of_week" in r and "session_count" in r for r in rows)


def test_activity_business_hours(client):
    resp = client.post("/api/v1/activity/business-hours", json=VALID_FILTERS, headers=HEADERS)
    assert resp.status_code == 200
    rows = resp.json()
    assert isinstance(rows, list)
    assert all("category" in r and "session_count" in r for r in rows)


# ── Tools router ──────────────────────────────────────────────────────────────

def test_tools_frequency(client):
    resp = client.post("/api/v1/tools/frequency", json=VALID_FILTERS, headers=HEADERS)
    assert resp.status_code == 200
    rows = resp.json()
    assert isinstance(rows, list)
    assert all("tool_name" in r and "call_count" in r for r in rows)


def test_tools_success_rate(client):
    resp = client.post("/api/v1/tools/success-rate", json=VALID_FILTERS, headers=HEADERS)
    assert resp.status_code == 200
    rows = resp.json()
    assert isinstance(rows, list)
    assert all("tool_name" in r and "success_rate" in r for r in rows)


# ── Sessions router ───────────────────────────────────────────────────────────

def test_sessions_duration_hist(client):
    """Returns raw per-session rows; binning is caller's responsibility."""
    resp = client.post("/api/v1/sessions/duration-hist", json=VALID_FILTERS, headers=HEADERS)
    assert resp.status_code == 200
    rows = resp.json()
    assert isinstance(rows, list)
    assert all("session_id" in r and "duration_mins" in r for r in rows)


def test_sessions_error_breakdown(client):
    resp = client.post("/api/v1/sessions/error-breakdown", json=VALID_FILTERS, headers=HEADERS)
    assert resp.status_code == 200
    rows = resp.json()
    assert isinstance(rows, list)
    assert all("status_code" in r and "count" in r for r in rows)
    assert len(rows) >= 1  # seed data has one 401 error


# ── Lifespan guard test ───────────────────────────────────────────────────────

def test_lifespan_raises_if_db_missing(monkeypatch):
    """Lifespan must refuse to start when DB file does not exist."""
    monkeypatch.setenv("API_KEY", API_KEY)
    monkeypatch.setenv("DB_PATH", "/nonexistent/path/analytics.duckdb")
    import src.api.main as main_mod
    monkeypatch.setattr(main_mod, "DB_PATH", "/nonexistent/path/analytics.duckdb")
    from src.api.main import app

    # Do NOT mock Path — let the real check run against a nonexistent path
    with pytest.raises(Exception):
        with TestClient(app):
            pass  # lifespan should raise before we get here
