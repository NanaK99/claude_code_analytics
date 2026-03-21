def init_db(conn) -> None:
    """Create all 6 tables in DuckDB. Drops existing tables first (idempotent)."""
    # Drop in reverse dependency order
    for table in ["api_errors", "tool_results", "tool_decisions",
                  "api_requests", "user_prompts", "employees"]:
        conn.execute(f"DROP TABLE IF EXISTS {table}")

    conn.execute("""
        CREATE TABLE employees (
            email         TEXT PRIMARY KEY,
            full_name     TEXT,
            practice      TEXT,
            level         TEXT,
            location      TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE user_prompts (
            session_id    TEXT,
            user_email    TEXT,
            timestamp     TIMESTAMP,
            prompt_length INTEGER,
            terminal_type TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE api_requests (
            session_id            TEXT,
            user_email            TEXT,
            timestamp             TIMESTAMP,
            model                 TEXT,
            input_tokens          INTEGER,
            output_tokens         INTEGER,
            cache_read_tokens     INTEGER,
            cache_creation_tokens INTEGER,
            cost_usd              DOUBLE,
            duration_ms           INTEGER,
            terminal_type         TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE tool_decisions (
            session_id    TEXT,
            user_email    TEXT,
            timestamp     TIMESTAMP,
            tool_name     TEXT,
            decision      TEXT,
            source        TEXT,
            terminal_type TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE tool_results (
            session_id          TEXT,
            user_email          TEXT,
            timestamp           TIMESTAMP,
            tool_name           TEXT,
            decision_type       TEXT,
            decision_source     TEXT,
            success             BOOLEAN,
            duration_ms         INTEGER,
            result_size_bytes   INTEGER,
            terminal_type       TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE api_errors (
            session_id    TEXT,
            user_email    TEXT,
            timestamp     TIMESTAMP,
            model         TEXT,
            error         TEXT,
            status_code   TEXT,
            attempt       INTEGER,
            duration_ms   INTEGER,
            terminal_type TEXT
        )
    """)
