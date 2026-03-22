import duckdb
from fastapi import Request


def get_db(request: Request) -> duckdb.DuckDBPyConnection:
    """FastAPI dependency: returns the shared read-only DuckDB connection from app state."""
    return request.app.state.db
