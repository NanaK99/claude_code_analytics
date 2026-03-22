from typing import List
from fastapi import APIRouter, Depends

from src.api.auth import verify_api_key
from src.api.deps import get_db
from src.api.schemas import (
    FiltersRequest,
    UsageByPracticeRow,
    UsageByLevelRow,
    UsageByLocationRow,
    TopEngineerRow,
)
from src.queries import (
    get_usage_by_practice,
    get_usage_by_level,
    get_usage_by_location,
    get_top_engineers,
)

router = APIRouter(
    prefix="/team",
    tags=["Team & Engineers"],
    dependencies=[Depends(verify_api_key)],
)


@router.post("/by-practice", response_model=List[UsageByPracticeRow])
def usage_by_practice(body: FiltersRequest, db=Depends(get_db)):
    return get_usage_by_practice(db, body.model_dump()).to_dict(orient="records")


@router.post("/by-level", response_model=List[UsageByLevelRow])
def usage_by_level(body: FiltersRequest, db=Depends(get_db)):
    return get_usage_by_level(db, body.model_dump()).to_dict(orient="records")


@router.post("/by-location", response_model=List[UsageByLocationRow])
def usage_by_location(body: FiltersRequest, db=Depends(get_db)):
    return get_usage_by_location(db, body.model_dump()).to_dict(orient="records")


@router.post("/top-engineers", response_model=List[TopEngineerRow])
def top_engineers(body: FiltersRequest, db=Depends(get_db)):
    return get_top_engineers(db, body.model_dump()).to_dict(orient="records")
