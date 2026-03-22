import os
import duckdb
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.api.routers import overview, costs, team, activity, tools, sessions

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


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


# Auth is enforced via dependencies=[Depends(verify_api_key)] on each router's APIRouter().
app.include_router(overview.router, prefix="/api/v1")
app.include_router(costs.router, prefix="/api/v1")
app.include_router(team.router, prefix="/api/v1")
app.include_router(activity.router, prefix="/api/v1")
app.include_router(tools.router, prefix="/api/v1")
app.include_router(sessions.router, prefix="/api/v1")
