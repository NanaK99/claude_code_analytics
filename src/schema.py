def init_db(conn) -> None:
    """Create all 6 tables in DuckDB. Drops existing tables first (idempotent)."""
    # Drop in reverse dependency order
    for table in ["api_errors", "tool_results", "tool_decisions",
                  "api_requests", "user_prompts", "employees"]:
        conn.execute(f"DROP TABLE IF EXISTS {table}")

    conn.execute("""
        CREATE TABLE employees (
            email         TEXT PRIMARY KEY,
            full_name     TEXT NOT NULL,
            practice      TEXT NOT NULL,
            level         TEXT NOT NULL,
            location      TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE user_prompts (
            session_id    TEXT      NOT NULL,
            user_email    TEXT      NOT NULL,
            timestamp     TIMESTAMP NOT NULL,
            prompt_length INTEGER   NOT NULL,
            terminal_type TEXT      NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE api_requests (
            session_id            TEXT      NOT NULL,
            user_email            TEXT      NOT NULL,
            timestamp             TIMESTAMP NOT NULL,
            model                 TEXT      NOT NULL,
            input_tokens          INTEGER   NOT NULL,
            output_tokens         INTEGER   NOT NULL,
            cache_read_tokens     INTEGER   NOT NULL,
            cache_creation_tokens INTEGER   NOT NULL,
            cost_usd              DOUBLE    NOT NULL,
            duration_ms           INTEGER   NOT NULL,
            terminal_type         TEXT      NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE tool_decisions (
            session_id    TEXT      NOT NULL,
            user_email    TEXT      NOT NULL,
            timestamp     TIMESTAMP NOT NULL,
            tool_name     TEXT      NOT NULL,
            decision      TEXT      NOT NULL,
            source        TEXT      NOT NULL,
            terminal_type TEXT      NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE tool_results (
            session_id          TEXT      NOT NULL,
            user_email          TEXT      NOT NULL,
            timestamp           TIMESTAMP NOT NULL,
            tool_name           TEXT      NOT NULL,
            decision_type       TEXT      NOT NULL,
            decision_source     TEXT      NOT NULL,
            success             BOOLEAN   NOT NULL,
            duration_ms         INTEGER   NOT NULL,
            result_size_bytes   INTEGER,
            terminal_type       TEXT      NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE api_errors (
            session_id    TEXT      NOT NULL,
            user_email    TEXT      NOT NULL,
            timestamp     TIMESTAMP NOT NULL,
            model         TEXT      NOT NULL,
            error         TEXT      NOT NULL,
            status_code   TEXT      NOT NULL,
            attempt       INTEGER   NOT NULL,
            duration_ms   INTEGER   NOT NULL,
            terminal_type TEXT      NOT NULL
        )
    """)
