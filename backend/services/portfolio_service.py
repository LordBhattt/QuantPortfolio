from uuid import UUID

from sqlalchemy import delete, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.errors import AppError
from backend.models.asset import assets
from backend.models.holding import holdings
from backend.models.portfolio import default_constraints, portfolios
from backend.schemas.portfolio import HoldingCreate, HoldingOut, PortfolioCreate, PortfolioOut, PortfolioUpdate


async def create_portfolio(payload: PortfolioCreate, user_id: UUID, db: AsyncSession) -> PortfolioOut:
    statement = (
        insert(portfolios)
        .values(
            user_id=user_id,
            name=payload.name,
            description=payload.description,
            base_currency=payload.base_currency,
            constraints=(payload.constraints.model_dump() if payload.constraints else default_constraints()),
        )
        .returning(portfolios)
    )
    result = await db.execute(statement)
    return PortfolioOut.model_validate(result.mappings().one())


async def list_portfolios(user_id: UUID, db: AsyncSession) -> list[PortfolioOut]:
    result = await db.execute(
        select(portfolios).where(portfolios.c.user_id == user_id).order_by(portfolios.c.created_at.desc())
    )
    return [PortfolioOut.model_validate(row) for row in result.mappings().all()]


async def get_portfolio(portfolio_id: UUID, user_id: UUID, db: AsyncSession) -> PortfolioOut:
    portfolio = await _get_portfolio_record(portfolio_id, user_id, db)
    return PortfolioOut.model_validate(portfolio)


async def update_portfolio(payload: PortfolioUpdate, portfolio_id: UUID, user_id: UUID, db: AsyncSession) -> PortfolioOut:
    current = await _get_portfolio_record(portfolio_id, user_id, db)
    values = payload.model_dump(exclude_none=True)
    if "constraints" in values and payload.constraints is not None:
        values["constraints"] = payload.constraints.model_dump()
    if not values:
        return PortfolioOut.model_validate(current)
    statement = update(portfolios).where(portfolios.c.id == portfolio_id).values(**values).returning(portfolios)
    result = await db.execute(statement)
    updated = result.mappings().one_or_none()
    if updated is None:
        raise AppError("Portfolio update failed", "portfolio_not_found", "Portfolio not found", 404)
    return PortfolioOut.model_validate(updated)


async def delete_portfolio(portfolio_id: UUID, user_id: UUID, db: AsyncSession) -> None:
    await _get_portfolio_record(portfolio_id, user_id, db)
    await db.execute(delete(holdings).where(holdings.c.portfolio_id == portfolio_id))
    await db.execute(delete(portfolios).where(portfolios.c.id == portfolio_id))


async def add_holding(payload: HoldingCreate, portfolio_id: UUID, user_id: UUID, db: AsyncSession) -> HoldingOut:
    await _get_portfolio_record(portfolio_id, user_id, db)
    asset_result = await db.execute(select(assets).where(assets.c.ticker == payload.ticker))
    if asset_result.mappings().first() is None:
        raise AppError("Holding creation failed", "asset_not_found", f"Asset {payload.ticker} not found", 404)

    statement = (
        insert(holdings)
        .values(
            portfolio_id=portfolio_id,
            ticker=payload.ticker,
            quantity=payload.quantity,
            avg_buy_price=payload.avg_buy_price,
            buy_currency=payload.buy_currency,
        )
        .returning(holdings)
    )
    result = await db.execute(statement)
    return HoldingOut.model_validate(result.mappings().one())


async def list_holdings(portfolio_id: UUID, user_id: UUID, db: AsyncSession) -> list[HoldingOut]:
    await _get_portfolio_record(portfolio_id, user_id, db)
    result = await db.execute(
        select(holdings).where(holdings.c.portfolio_id == portfolio_id).order_by(holdings.c.created_at.asc())
    )
    return [HoldingOut.model_validate(row) for row in result.mappings().all()]


async def delete_holding(portfolio_id: UUID, holding_id: UUID, user_id: UUID, db: AsyncSession) -> None:
    await _get_portfolio_record(portfolio_id, user_id, db)
    result = await db.execute(
        delete(holdings)
        .where(holdings.c.id == holding_id, holdings.c.portfolio_id == portfolio_id)
        .returning(holdings.c.id)
    )
    if result.scalar_one_or_none() is None:
        raise AppError("Holding delete failed", "holding_not_found", "Holding not found", 404)


async def load_portfolio_snapshot(
    portfolio_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> tuple[dict, list[dict], list[dict]]:
    portfolio = await _get_portfolio_record(portfolio_id, user_id, db)
    holdings_result = await db.execute(select(holdings).where(holdings.c.portfolio_id == portfolio_id))
    holding_rows = [dict(row) for row in holdings_result.mappings().all()]
    tickers = [row["ticker"] for row in holding_rows]

    asset_rows: list[dict] = []
    if tickers:
        asset_result = await db.execute(select(assets).where(assets.c.ticker.in_(tickers)))
        asset_rows = [dict(row) for row in asset_result.mappings().all()]

    return portfolio, holding_rows, asset_rows


async def _get_portfolio_record(portfolio_id: UUID, user_id: UUID, db: AsyncSession) -> dict:
    result = await db.execute(
        select(portfolios).where(portfolios.c.id == portfolio_id, portfolios.c.user_id == user_id)
    )
    row = result.mappings().first()
    if row is None:
        raise AppError("Portfolio not found", "portfolio_not_found", "Portfolio not found", 404)
    return dict(row)
