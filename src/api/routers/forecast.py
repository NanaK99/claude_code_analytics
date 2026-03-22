from fastapi import APIRouter, Depends

from src.api.auth import verify_api_key
from src.api.deps import get_db
from src.api.schemas import FiltersRequest, ForecastSummaryResponse
from src.forecasting import build_forecast_summary
from src.queries import get_daily_cost_totals

_FORECAST_PERIODS = 14

router = APIRouter(
    prefix="/forecast",
    tags=["Forecast & Anomalies"],
    dependencies=[Depends(verify_api_key)],
)


@router.post("/summary", response_model=ForecastSummaryResponse)
def forecast_summary(body: FiltersRequest, db=Depends(get_db)):
    filters = body.model_dump()
    daily_costs = get_daily_cost_totals(db, filters)
    return build_forecast_summary(daily_costs, periods=_FORECAST_PERIODS, filters=filters)
