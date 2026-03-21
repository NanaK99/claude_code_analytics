import duckdb
import pytest
from src.schema import init_db


def test_init_db_creates_all_six_tables():
    conn = duckdb.connect(":memory:")
    init_db(conn)
    tables = {row[0] for row in conn.execute("SHOW TABLES").fetchall()}
    assert tables == {
        "employees", "user_prompts", "api_requests",
        "tool_decisions", "tool_results", "api_errors",
    }


def test_init_db_is_idempotent():
    conn = duckdb.connect(":memory:")
    init_db(conn)
    conn.execute(
        "INSERT INTO employees VALUES ('a@b.com', 'Alice', 'ML Engineering', 'L5', 'Germany')"
    )
    init_db(conn)  # second call must drop and recreate
    count = conn.execute("SELECT COUNT(*) FROM employees").fetchone()[0]
    assert count == 0


def test_api_requests_accepts_valid_row():
    conn = duckdb.connect(":memory:")
    init_db(conn)
    conn.execute("""
        INSERT INTO api_requests VALUES
        ('sess1', 'a@b.com', '2025-12-03 00:06:00', 'claude-sonnet-4-6',
         100, 200, 5000, 0, 0.005, 9078, 'vscode')
    """)
    assert conn.execute("SELECT COUNT(*) FROM api_requests").fetchone()[0] == 1


def test_tool_results_result_size_is_nullable():
    conn = duckdb.connect(":memory:")
    init_db(conn)
    conn.execute("""
        INSERT INTO tool_results VALUES
        ('sess1', 'a@b.com', '2025-12-03 00:08:00',
         'Read', 'accept', 'config', true, 61, NULL, 'vscode')
    """)
    val = conn.execute("SELECT result_size_bytes FROM tool_results").fetchone()[0]
    assert val is None
