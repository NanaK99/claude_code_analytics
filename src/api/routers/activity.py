from typing import List
from fastapi import APIRouter, Depends

from src.api.auth import verify_api_key
from src.api.deps import get_db
from src.api.schemas import (
    FiltersRequest,
    HourlyHeatmapRow,
    DayOfWeekRow,
    BusinessHoursRow,
)
from src.queries import (
    get_hourly_heatmap,
    get_day_of_week_counts,
    get_business_hours_split,
)

router = APIRouter(
    prefix="/activity",
    tags=["Activity Patterns"],
    dependencies=[Depends(verify_api_key)],
)


@router.post("/hourly-heatmap", response_model=List[HourlyHeatmapRow])
def hourly_heatmap(body: FiltersRequest, db=Depends(get_db)):
    return get_hourly_heatmap(db, body.model_dump()).to_dict(orient="records")


@router.post("/day-of-week", response_model=List[DayOfWeekRow])
def day_of_week(body: FiltersRequest, db=Depends(get_db)):
    return get_day_of_week_counts(db, body.model_dump()).to_dict(orient="records")


@router.post("/business-hours", response_model=List[BusinessHoursRow])
def business_hours(body: FiltersRequest, db=Depends(get_db)):
    return get_business_hours_split(db, body.model_dump()).to_dict(orient="records")
