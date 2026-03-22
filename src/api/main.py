import os
import duckdb
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

DB_PATH = os.getenv("DB_PATH", "db/analytics.duckdb")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if not Path(DB_PATH).exists():
        raise RuntimeError(
            f"Database not found at '{DB_PATH}'. Run: conda run -n provectus_task python ingest.py"
        )
    if not os.getenv("API_KEY"):
        raise RuntimeError("API_KEY environment variable is required.")
    app.state.db = duckdb.connect(DB_PATH, read_only=True)
    yield
    app.state.db.close()


app = FastAPI(
    title="Claude Code Analytics API",
    version="1.0.0",
    description="Programmatic access to Claude Code telemetry analytics.",
    lifespan=lifespan,
)


@app.middleware("http")
async def require_api_key(request: Request, call_next):
    """Enforce API key auth before routing so unmatched routes also get 403, not 404."""
    expected = os.getenv("API_KEY")
    key = request.headers.get("X-API-Key")
    if not expected or key != expected:
        return JSONResponse(status_code=403, content={"detail": "Invalid or missing API key"})
    return await call_next(request)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# Routers registered in Tasks 6-11
