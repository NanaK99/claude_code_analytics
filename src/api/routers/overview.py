from typing import List
from fastapi import APIRouter, Depends

from src.api.auth import verify_api_key
from src.api.deps import get_db
from src.api.schemas import (
    FiltersRequest,
    KpiMetricsResponse,
    DailySessionRow,
    SessionKpisResponse,
    CacheSavingsResponse,
)
from src.queries import (
    get_kpi_metrics,
    get_daily_sessions,
    get_session_kpis,
    get_cache_savings,
)

router = APIRouter(
    prefix="/overview",
    tags=["Overview"],
    dependencies=[Depends(verify_api_key)],
)


@router.post("/kpi-metrics", response_model=KpiMetricsResponse)
def kpi_metrics(body: FiltersRequest, db=Depends(get_db)):
    return get_kpi_metrics(db, body.model_dump())


@router.post("/daily-sessions", response_model=List[DailySessionRow])
def daily_sessions(body: FiltersRequest, db=Depends(get_db)):
    return get_daily_sessions(db, body.model_dump()).to_dict(orient="records")


@router.post("/session-kpis", response_model=SessionKpisResponse)
def session_kpis(body: FiltersRequest, db=Depends(get_db)):
    return get_session_kpis(db, body.model_dump())


@router.post("/cache-savings", response_model=CacheSavingsResponse)
def cache_savings(body: FiltersRequest, db=Depends(get_db)):
    return CacheSavingsResponse(cache_savings_usd=get_cache_savings(db, body.model_dump()))
