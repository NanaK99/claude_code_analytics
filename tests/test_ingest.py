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


def test_ingest_counts_malformed_json_line():
    """A line that is not valid JSON increments malformed count."""
    import tempfile, os
    conn = duckdb.connect(":memory:")
    init_db(conn)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write("this is not json\n")
        tmp_path = f.name
    try:
        counts = run_ingest(conn, telemetry_path=tmp_path, employees_path=str(FIXTURES / "sample_employees.csv"))
        assert counts["malformed"] == 1
        assert counts["ingested"] == 0
    finally:
        os.unlink(tmp_path)


def test_ingest_counts_unknown_event_type():
    """An event with an unrecognised body string increments unknown_types count."""
    import tempfile, os, json
    conn = duckdb.connect(":memory:")
    init_db(conn)
    batch = {"messageType": "DATA_MESSAGE", "logEvents": [{"id": "1", "timestamp": 0, "message": json.dumps({
        "body": "claude_code.unknown_future_event",
        "attributes": {"session.id": "s1", "user.email": "x@x.com", "event.timestamp": "2025-12-10T10:00:00.000Z", "terminal.type": "vscode"}
    })}]}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write(json.dumps(batch) + "\n")
        tmp_path = f.name
    try:
        counts = run_ingest(conn, telemetry_path=tmp_path, employees_path=str(FIXTURES / "sample_employees.csv"))
        assert counts["unknown_types"] == 1
        assert counts["ingested"] == 0
    finally:
        os.unlink(tmp_path)


def test_ingest_counts_missing_required_field():
    """An event missing a required field increments missing_fields count."""
    import tempfile, os, json
    conn = duckdb.connect(":memory:")
    init_db(conn)
    # user_prompt missing prompt_length
    batch = {"messageType": "DATA_MESSAGE", "logEvents": [{"id": "1", "timestamp": 0, "message": json.dumps({
        "body": "claude_code.user_prompt",
        "attributes": {"session.id": "s1", "user.email": "x@x.com", "event.timestamp": "2025-12-10T10:00:00.000Z", "terminal.type": "vscode"}
    })}]}
    with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
        f.write(json.dumps(batch) + "\n")
        tmp_path = f.name
    try:
        counts = run_ingest(conn, telemetry_path=tmp_path, employees_path=str(FIXTURES / "sample_employees.csv"))
        assert counts["missing_fields"] == 1
        assert counts["ingested"] == 0
    finally:
        os.unlink(tmp_path)
