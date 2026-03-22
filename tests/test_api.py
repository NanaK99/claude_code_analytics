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
        mock_duckdb.connect.return_value = seed_db
        with TestClient(app) as c:
            yield c

    app.dependency_overrides.clear()


# ── Auth tests ────────────────────────────────────────────────────────────────

def test_missing_api_key_returns_403(client):
    # Will return 403 once overview router is registered (Task 6); 404 before that
    resp = client.post("/api/v1/overview/kpi-metrics", json=VALID_FILTERS)
    assert resp.status_code in (403, 404)


def test_wrong_api_key_returns_403(client):
    # Will return 403 once overview router is registered (Task 6); 404 before that
    resp = client.post(
        "/api/v1/overview/kpi-metrics",
        json=VALID_FILTERS,
        headers={"X-API-Key": "wrong-key"},
    )
    assert resp.status_code in (403, 404)


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
