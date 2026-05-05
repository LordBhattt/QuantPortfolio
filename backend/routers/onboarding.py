from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from backend.data_types import CurrentUser
from backend.database import get_db
from backend.dependencies import get_current_user
from backend.schemas.onboarding import InvestorProfileCreate, InvestorProfileOut, PortfolioRecommendation
from backend.services.onboarding_service import recommend_portfolio, upsert_investor_profile


router = APIRouter(prefix="/api/v1/onboarding", tags=["onboarding"])


@router.post("/profile", response_model=InvestorProfileOut)
async def upsert_profile(
    payload: InvestorProfileCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> InvestorProfileOut:
    return await upsert_investor_profile(payload, current_user.id, db)


@router.post("/recommend", response_model=list[PortfolioRecommendation])
async def recommend_profile(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[PortfolioRecommendation]:
    return await recommend_portfolio(current_user.id, db)