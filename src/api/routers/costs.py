from typing import List
from fastapi import APIRouter, Depends

from src.api.auth import verify_api_key
from src.api.deps import get_db
from src.api.schemas import (
    FiltersRequest,
    CostByPracticeRow,
    CostByLevelRow,
    TokenBreakdownRow,
    ModelDistributionRow,
    AvgCostTrendRow,
    CacheHitRateResponse,
)
from src.queries import (
    get_cost_by_practice_over_time,
    get_cost_by_level_over_time,
    get_token_breakdown,
    get_model_distribution,
    get_avg_cost_per_session_over_time,
    get_cache_hit_rate,
)

router = APIRouter(
    prefix="/costs",
    tags=["Costs & Tokens"],
    dependencies=[Depends(verify_api_key)],
)


@router.post("/by-practice", response_model=List[CostByPracticeRow])
def cost_by_practice(body: FiltersRequest, db=Depends(get_db)):
    return get_cost_by_practice_over_time(db, body.model_dump()).to_dict(orient="records")


@router.post("/by-level", response_model=List[CostByLevelRow])
def cost_by_level(body: FiltersRequest, db=Depends(get_db)):
    return get_cost_by_level_over_time(db, body.model_dump()).to_dict(orient="records")


@router.post("/token-breakdown", response_model=List[TokenBreakdownRow])
def token_breakdown(body: FiltersRequest, db=Depends(get_db)):
    return get_token_breakdown(db, body.model_dump()).to_dict(orient="records")


@router.post("/model-distribution", response_model=List[ModelDistributionRow])
def model_distribution(body: FiltersRequest, db=Depends(get_db)):
    return get_model_distribution(db, body.model_dump()).to_dict(orient="records")


@router.post("/avg-cost-trend", response_model=List[AvgCostTrendRow])
def avg_cost_trend(body: FiltersRequest, db=Depends(get_db)):
    return get_avg_cost_per_session_over_time(db, body.model_dump()).to_dict(orient="records")


@router.post("/cache-hit-rate", response_model=CacheHitRateResponse)
def cache_hit_rate(body: FiltersRequest, db=Depends(get_db)):
    return CacheHitRateResponse(cache_hit_rate=get_cache_hit_rate(db, body.model_dump()))
