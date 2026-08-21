from fastapi import APIRouter, Depends, Query

from backend.data_types import CurrentUser
from backend.dependencies import get_current_user
from backend.quant.backtest import DEFAULT_LOOKBACK_DAYS, DEFAULT_TRANSACTION_COST_BPS
from backend.schemas.backtest import BacktestResponse
from backend.services.backtest_service import run_backtest

router = APIRouter(prefix="/api/v1/backtest", tags=["backtest"])


@router.get("/", response_model=BacktestResponse)
async def get_backtest(
    lookback_days: int = Query(default=DEFAULT_LOOKBACK_DAYS, ge=126, le=1260),
    transaction_cost_bps: float = Query(default=DEFAULT_TRANSACTION_COST_BPS, ge=0.0, le=200.0),
    baseline: str = Query(default="equal_weight"),
    current_user: CurrentUser = Depends(get_current_user),
) -> BacktestResponse:
    del current_user
    return await run_backtest(
        lookback_days=lookback_days,
        transaction_cost_bps=transaction_cost_bps,
        baseline=baseline,
    )
