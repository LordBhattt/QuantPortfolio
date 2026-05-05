from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from backend.data_types import CurrentUser
from backend.database import get_db
from backend.dependencies import get_current_user, get_fetcher
from backend.quant.data_fetcher import DataFetcher
from backend.rate_limit import limiter
from backend.schemas.optimization import OptimizationRequest, OptimizationResult
from backend.services.optimization_service import run_optimization

router = APIRouter(prefix="/api/v1/optimize", tags=["optimization"])


@router.post("/", response_model=OptimizationResult)
@limiter.limit("5/minute")
async def optimize_portfolio(
    request: Request,
    payload: OptimizationRequest,
    db: AsyncSession = Depends(get_db),
    fetcher: DataFetcher = Depends(get_fetcher),
    current_user: CurrentUser = Depends(get_current_user),
) -> OptimizationResult:
    del request
    return await run_optimization(payload, current_user.id, db, fetcher)
