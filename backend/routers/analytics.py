from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.data_types import CurrentUser
from backend.database import get_db
from backend.dependencies import get_current_user, get_fetcher
from backend.quant.data_fetcher import DataFetcher
from backend.schemas.analytics import FactorExposure, PortfolioAnalytics
from backend.services.analytics_service import get_factor_exposure, get_portfolio_analytics

router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


@router.get("/{portfolio_id}", response_model=PortfolioAnalytics)
async def portfolio_analytics(
    portfolio_id: UUID,
    db: AsyncSession = Depends(get_db),
    fetcher: DataFetcher = Depends(get_fetcher),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioAnalytics:
    return await get_portfolio_analytics(portfolio_id, current_user.id, db, fetcher)


@router.get("/{portfolio_id}/factors", response_model=FactorExposure)
async def factor_exposure(
    portfolio_id: UUID,
    db: AsyncSession = Depends(get_db),
    fetcher: DataFetcher = Depends(get_fetcher),
    current_user: CurrentUser = Depends(get_current_user),
) -> FactorExposure:
    return await get_factor_exposure(portfolio_id, current_user.id, db, fetcher)
