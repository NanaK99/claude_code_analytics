import duckdb
import pytest
from pathlib import Path
from src.schema import init_db
from ingest import run_ingest

FIXTURES = Path(__file__).parent / "fixtures"


def test_ingest_populates_all_tables():
    conn = duckdb.connect(":memory:")
    init_db(conn)
    run_ingest(
        conn,
        telemetry_path=str(FIXTURES / "sample_telemetry.jsonl"),
        employees_path=str(FIXTURES / "sample_employees.csv"),
    )
    assert conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0] == 2
    assert conn.execute("SELECT COUNT(*) FROM user_prompts").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM api_requests").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM tool_decisions").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM tool_results").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM api_errors").fetchone()[0] == 1


def test_ingest_returns_correct_counts():
    conn = duckdb.connect(":memory:")
    init_db(conn)
    counts = run_ingest(
        conn,
        telemetry_path=str(FIXTURES / "sample_telemetry.jsonl"),
        employees_path=str(FIXTURES / "sample_employees.csv"),
    )
    assert counts["ingested"] == 5
    assert counts["malformed"] == 0
    assert counts["missing_fields"] == 0
    assert counts["unknown_types"] == 0
