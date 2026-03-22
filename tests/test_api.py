import os
import unittest.mock as mock
import duckdb
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
