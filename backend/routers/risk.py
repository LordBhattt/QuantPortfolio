from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.data_types import CurrentUser
from backend.database import get_db
from backend.dependencies import get_current_user, get_fetcher
from backend.quant.data_fetcher import DataFetcher
from backend.schemas.risk import MonteCarloResult, RiskMetrics
from backend.services.risk_service import compute_risk_metrics, run_monte_carlo

router = APIRouter(prefix="/api/v1/risk", tags=["risk"])


@router.get("/{portfolio_id}", response_model=RiskMetrics)
async def get_risk_metrics(
    portfolio_id: UUID,
    db: AsyncSession = Depends(get_db),
    fetcher: DataFetcher = Depends(get_fetcher),
    current_user: CurrentUser = Depends(get_current_user),
) -> RiskMetrics:
    return await compute_risk_metrics(portfolio_id, current_user.id, db, fetcher)


@router.get("/{portfolio_id}/monte-carlo", response_model=MonteCarloResult)
async def get_monte_carlo(
    portfolio_id: UUID,
    n_paths: int = Query(default=1000, ge=100, le=10000),
    horizon_days: int = Query(default=252, ge=30, le=1260),
    db: AsyncSession = Depends(get_db),
    fetcher: DataFetcher = Depends(get_fetcher),
    current_user: CurrentUser = Depends(get_current_user),
) -> MonteCarloResult:
    return await run_monte_carlo(
        portfolio_id=portfolio_id,
        user_id=current_user.id,
        db=db,
        fetcher=fetcher,
        n_paths=n_paths,
        horizon_days=horizon_days,
    )
