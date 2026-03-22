from typing import List
from fastapi import APIRouter, Depends

from src.api.auth import verify_api_key
from src.api.deps import get_db
from src.api.schemas import (
    FiltersRequest,
    ToolFrequencyRow,
    ToolAcceptRejectRow,
    ToolSuccessRateRow,
    ToolExecutionTimeRow,
)
from src.queries import (
    get_tool_frequency,
    get_tool_accept_reject,
    get_tool_success_rate,
    get_tool_execution_time,
)

router = APIRouter(
    prefix="/tools",
    tags=["Tool Behavior"],
    dependencies=[Depends(verify_api_key)],
)


@router.post("/frequency", response_model=List[ToolFrequencyRow])
def tool_frequency(body: FiltersRequest, db=Depends(get_db)):
    return get_tool_frequency(db, body.model_dump()).to_dict(orient="records")


@router.post("/accept-reject", response_model=List[ToolAcceptRejectRow])
def tool_accept_reject(body: FiltersRequest, db=Depends(get_db)):
    return get_tool_accept_reject(db, body.model_dump()).to_dict(orient="records")


@router.post("/success-rate", response_model=List[ToolSuccessRateRow])
def tool_success_rate(body: FiltersRequest, db=Depends(get_db)):
    return get_tool_success_rate(db, body.model_dump()).to_dict(orient="records")


@router.post("/execution-time", response_model=List[ToolExecutionTimeRow])
def tool_execution_time(body: FiltersRequest, db=Depends(get_db)):
    return get_tool_execution_time(db, body.model_dump()).to_dict(orient="records")
