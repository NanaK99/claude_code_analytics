from typing import List
from fastapi import APIRouter, Depends

from src.api.auth import verify_api_key
from src.api.deps import get_db
from src.api.schemas import (
    FiltersRequest,
    SessionDurationRow,
    SessionCostByPracticeRow,
    ApiLatencyRow,
    ErrorBreakdownRow,
    LevelCostCorrelationRow,
)
from src.queries import (
    get_session_duration_hist,
    get_session_cost_by_practice,
    get_api_latency_by_model,
    get_error_breakdown,
    get_level_cost_correlation,
)

router = APIRouter(
    prefix="/sessions",
    tags=["Session Intelligence"],
    dependencies=[Depends(verify_api_key)],
)


@router.post("/duration-hist", response_model=List[SessionDurationRow])
def session_duration_hist(body: FiltersRequest, db=Depends(get_db)):
    return get_session_duration_hist(db, body.model_dump()).to_dict(orient="records")


@router.post("/cost-by-practice", response_model=List[SessionCostByPracticeRow])
def session_cost_by_practice(body: FiltersRequest, db=Depends(get_db)):
    return get_session_cost_by_practice(db, body.model_dump()).to_dict(orient="records")


@router.post("/api-latency", response_model=List[ApiLatencyRow])
def api_latency(body: FiltersRequest, db=Depends(get_db)):
    return get_api_latency_by_model(db, body.model_dump()).to_dict(orient="records")


@router.post("/error-breakdown", response_model=List[ErrorBreakdownRow])
def error_breakdown(body: FiltersRequest, db=Depends(get_db)):
    return get_error_breakdown(db, body.model_dump()).to_dict(orient="records")


@router.post("/level-cost-correlation", response_model=List[LevelCostCorrelationRow])
def level_cost_correlation(body: FiltersRequest, db=Depends(get_db)):
    return get_level_cost_correlation(db, body.model_dump()).to_dict(orient="records")
