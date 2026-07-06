import asyncio
import math
from uuid import UUID

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.dependencies import get_fetcher
from backend.errors import AppError
from backend.models.asset import assets
from backend.models.investor_profile import investor_profiles
from backend.models.portfolio import constraints_for_risk_score
from backend.schemas.onboarding import InvestorProfileCreate, InvestorProfileOut, PortfolioRecommendation
from backend.schemas.optimization import PortfolioConstraints
from backend.schemas.portfolio import PortfolioCreate
from backend.services.portfolio_builder import build_recommended_portfolio
from backend.services.portfolio_service import create_portfolio, list_portfolios, update_portfolio
from backend.schemas.portfolio import PortfolioUpdate


BASE_RISK_SCORES: dict[str, dict[str, int]] = {
    "conservative": {"short_term": 4, "medium_term": 6, "long_term": 8},
    "moderate": {"short_term": 8, "medium_term": 12, "long_term": 14},
    "aggressive": {"short_term": 12, "medium_term": 16, "long_term": 18},
}


def compute_risk_score(payload: InvestorProfileCreate) -> int:
    raw_score = BASE_RISK_SCORES[payload.risk_appetite][payload.investment_horizon]

    if payload.age_group in {"18-25", "26-35"}:
        raw_score += 2
    elif payload.age_group == "50+":
        raw_score -= 2

    if payload.income_stability == "variable":
        raw_score -= 1

    if not payload.existing_investments:
        raw_score -= 1

    return max(1, min(10, math.ceil(raw_score / 2)))


async def upsert_investor_profile(payload: InvestorProfileCreate, user_id: UUID, db: AsyncSession) -> InvestorProfileOut:
    profile_values = payload.model_dump()
    profile_values["user_id"] = user_id
    profile_values["risk_score"] = compute_risk_score(payload)

    result = await db.execute(select(investor_profiles.c.id).where(investor_profiles.c.user_id == user_id))
    profile_id = result.scalar_one_or_none()

    if profile_id is None:
        statement = insert(investor_profiles).values(**profile_values).returning(investor_profiles)
    else:
        statement = (
            update(investor_profiles)
            .where(investor_profiles.c.id == profile_id)
            .values(**profile_values, updated_at=func.now())
            .returning(investor_profiles)
        )

    result = await db.execute(statement)
    row = result.mappings().one_or_none()
    if row is None:
        raise AppError("Onboarding profile failed", "profile_upsert_failed", "Unable to save investor profile", 500)
    return InvestorProfileOut.model_validate(row)


async def recommend_portfolio(user_id: UUID, db: AsyncSession) -> list[PortfolioRecommendation]:
    profile = await get_investor_profile(user_id, db)
    risk_constraints = constraints_for_risk_score(profile.risk_score)
    portfolio_constraints = PortfolioConstraints(**risk_constraints)

    portfolios = await list_portfolios(user_id, db)
    if not portfolios:
        await create_portfolio(
            PortfolioCreate(
                name="My Recommended Portfolio",
                description="Auto-created from investor profile",
                constraints=portfolio_constraints,
            ),
            user_id,
            db,
        )
    else:
        # Update existing portfolio constraints to match the new risk profile
        target = portfolios[0]
        await update_portfolio(
            PortfolioUpdate(constraints=portfolio_constraints),
            target.id,
            user_id,
            db,
        )

    allocations = build_recommended_portfolio(profile.risk_score, profile.investment_amount)
    price_map = await _get_reference_prices(allocations, db)

    return [
        PortfolioRecommendation.model_validate(
            {
                **row,
                "current_price_inr": price_map.get(row["ticker"]),
            }
        )
        for row in allocations
    ]


async def get_investor_profile(user_id: UUID, db: AsyncSession) -> InvestorProfileOut:
    result = await db.execute(select(investor_profiles).where(investor_profiles.c.user_id == user_id))
    row = result.mappings().first()
    if row is None:
        raise AppError("Onboarding profile not found", "profile_not_found", "Investor profile not found", 404)
    return InvestorProfileOut.model_validate(row)


async def _get_reference_prices(
    allocations: list[dict[str, float | str]],
    db: AsyncSession,
) -> dict[str, float]:
    try:
        fetcher = get_fetcher()
    except AppError:
        return {}

    tickers = [str(row["ticker"]) for row in allocations]
    result = await db.execute(select(assets).where(assets.c.ticker.in_(tickers)))
    asset_rows = [dict(row) for row in result.mappings().all()]
    if not asset_rows:
        return {}

    async def fetch_price(asset_row: dict) -> tuple[str, float | None]:
        try:
            price = await fetcher.get_latest_price_in_inr(
                asset_row["ticker"],
                asset_row["data_source"],
                exchange=asset_row.get("exchange"),
                currency=asset_row.get("currency"),
            )
            return asset_row["ticker"], price
        except Exception:
            return asset_row["ticker"], None

    pairs = await asyncio.gather(*[fetch_price(row) for row in asset_rows])
    return {ticker: price for ticker, price in pairs if price is not None}