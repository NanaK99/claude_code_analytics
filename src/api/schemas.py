import datetime
from typing import Optional, List, Literal
from pydantic import BaseModel

from src.queries import Filters


class FiltersRequest(Filters):
    """
    Re-uses all Filters validators (date ordering, valid practices/levels/locations).
    Subclassed (not aliased) so FastAPI renders it as 'FiltersRequest' in /docs.
    """
    pass


# ── Scalar responses ───────────────────────────────────────────────────────────

class KpiMetricsResponse(BaseModel):
    total_sessions: int
    active_engineers: int
    total_cost: float
    error_rate: float


class SessionKpisResponse(BaseModel):
    avg_duration_mins: float
    avg_prompts_per_session: float


class CacheSavingsResponse(BaseModel):
    cache_savings_usd: float


class CacheHitRateResponse(BaseModel):
    cache_hit_rate: float


# ── Overview ──────────────────────────────────────────────────────────────────

class DailySessionRow(BaseModel):
    date: datetime.date
    session_count: int


# ── Costs & Tokens ────────────────────────────────────────────────────────────

class CostByPracticeRow(BaseModel):
    date: datetime.date
    practice: str
    total_cost: float


class CostByLevelRow(BaseModel):
    date: datetime.date
    level: str
    total_cost: float


class TokenBreakdownRow(BaseModel):
    token_type: str
    total: int


class ModelDistributionRow(BaseModel):
    model: str
    call_count: int
    total_cost: float


class AvgCostTrendRow(BaseModel):
    date: datetime.date
    avg_cost_per_session: float


# ── Team & Engineers ──────────────────────────────────────────────────────────

class UsageByPracticeRow(BaseModel):
    practice: str
    session_count: int
    total_cost: float


class UsageByLevelRow(BaseModel):
    level: str
    session_count: int


class UsageByLocationRow(BaseModel):
    location: str
    session_count: int


class TopEngineerRow(BaseModel):
    full_name: str
    practice: str
    level: str
    session_count: int
    total_cost: float
    avg_cost_per_session: float
    preferred_model: Optional[str] = None


# ── Activity Patterns ─────────────────────────────────────────────────────────

class HourlyHeatmapRow(BaseModel):
    hour: int
    day_of_week: str
    session_count: int


class DayOfWeekRow(BaseModel):
    day_of_week: str
    session_count: int


class BusinessHoursRow(BaseModel):
    category: str
    session_count: int


# ── Tool Behavior ─────────────────────────────────────────────────────────────

class ToolFrequencyRow(BaseModel):
    tool_name: str
    call_count: int


class ToolAcceptRejectRow(BaseModel):
    tool_name: str
    accept_count: int
    reject_count: int


class ToolSuccessRateRow(BaseModel):
    tool_name: str
    success_rate: float


class ToolExecutionTimeRow(BaseModel):
    tool_name: str
    avg_duration_ms: float


# ── Session Intelligence ───────────────────────────────────────────────────────

class SessionDurationRow(BaseModel):
    """Raw per-session data. Binning for histogram display is the caller's responsibility."""
    session_id: str
    duration_mins: float


class SessionCostByPracticeRow(BaseModel):
    session_id: str
    practice: str
    total_cost: float


class ApiLatencyRow(BaseModel):
    model: str
    avg_duration_ms: float


class ErrorBreakdownRow(BaseModel):
    status_code: str
    count: int


class LevelCostCorrelationRow(BaseModel):
    level: str
    avg_cost_per_session: float


# ── Forecast Summary ─────────────────────────────────────────────────────────

class ForecastHistoryRow(BaseModel):
    ds: datetime.date
    y: float


class ForecastRow(BaseModel):
    ds: datetime.date
    yhat: float
    yhat_lower: float
    yhat_upper: float


class ForecastAnomalyRow(BaseModel):
    ds: datetime.date
    actual_cost: float
    expected_cost: float
    residual: float


class ForecastMetrics(BaseModel):
    mae: Optional[float] = None
    mape: Optional[float] = None
    coverage: Optional[float] = None


class ForecastSummaryResponse(BaseModel):
    status: Literal["ok", "insufficient_data", "forecast_error"]
    message: Optional[str] = None
    history: List[ForecastHistoryRow]
    forecast: List[ForecastRow]
    metrics: Optional[ForecastMetrics] = None
    anomalies: List[ForecastAnomalyRow]
