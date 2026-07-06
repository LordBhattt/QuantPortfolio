from uuid import UUID

from collections.abc import Iterable

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
    await db.commit()
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
    await db.commit()
    return PortfolioOut.model_validate(updated)


async def delete_portfolio(portfolio_id: UUID, user_id: UUID, db: AsyncSession) -> None:
    await _get_portfolio_record(portfolio_id, user_id, db)
    await db.execute(delete(holdings).where(holdings.c.portfolio_id == portfolio_id))
    await db.execute(delete(portfolios).where(portfolios.c.id == portfolio_id))
    await db.commit()


async def add_holding(payload: HoldingCreate, portfolio_id: UUID, user_id: UUID, db: AsyncSession) -> HoldingOut:
    await _get_portfolio_record(portfolio_id, user_id, db)
    result = await _upsert_holdings(
        portfolio_id=portfolio_id,
        payloads=[payload],
        db=db,
    )
    await db.commit()
    return result[0]


async def add_holdings(
    payloads: list[HoldingCreate],
    portfolio_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> list[HoldingOut]:
    await _get_portfolio_record(portfolio_id, user_id, db)
    if not payloads:
        return []

    holdings_created = await _upsert_holdings(portfolio_id=portfolio_id, payloads=payloads, db=db)
    await db.commit()
    return holdings_created


async def list_holdings(portfolio_id: UUID, user_id: UUID, db: AsyncSession) -> list[HoldingOut]:
    await _get_portfolio_record(portfolio_id, user_id, db)
    result = await db.execute(
        select(holdings).where(holdings.c.portfolio_id == portfolio_id).order_by(holdings.c.created_at.asc())
    )
    return [HoldingOut.model_validate(row) for row in _merge_holdings_rows(result.mappings().all())]


async def delete_holding(portfolio_id: UUID, holding_id: UUID, user_id: UUID, db: AsyncSession) -> None:
    await _get_portfolio_record(portfolio_id, user_id, db)
    result = await db.execute(
        delete(holdings)
        .where(holdings.c.id == holding_id, holdings.c.portfolio_id == portfolio_id)
        .returning(holdings.c.id)
    )
    if result.scalar_one_or_none() is None:
        raise AppError("Holding delete failed", "holding_not_found", "Holding not found", 404)
    await db.commit()


async def load_portfolio_snapshot(
    portfolio_id: UUID,
    user_id: UUID,
    db: AsyncSession,
) -> tuple[dict, list[dict], list[dict]]:
    portfolio = await _get_portfolio_record(portfolio_id, user_id, db)
    holdings_result = await db.execute(select(holdings).where(holdings.c.portfolio_id == portfolio_id))
    holding_rows = _merge_holdings_rows(holdings_result.mappings().all())
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


async def _upsert_holdings(
    portfolio_id: UUID,
    payloads: Iterable[HoldingCreate],
    db: AsyncSession,
) -> list[HoldingOut]:
    normalized: dict[str, dict[str, float | str]] = {}
    for payload in payloads:
        ticker = payload.ticker
        buy_currency = payload.buy_currency.upper()
        bucket = normalized.setdefault(
            ticker,
            {
                "quantity": 0.0,
                "cost": 0.0,
                "buy_currency": buy_currency,
            },
        )
        if str(bucket["buy_currency"]) != buy_currency:
            raise AppError(
                "Holding creation failed",
                "currency_mismatch",
                f"Mixed currencies are not supported for {ticker}",
                400,
            )
        quantity = float(payload.quantity)
        bucket["quantity"] = float(bucket["quantity"]) + quantity
        bucket["cost"] = float(bucket["cost"]) + (quantity * float(payload.avg_buy_price))

    tickers = list(normalized)
    asset_result = await db.execute(select(assets).where(assets.c.ticker.in_(tickers)))
    asset_rows = {row["ticker"]: row for row in asset_result.mappings().all()}
    missing_tickers = [ticker for ticker in tickers if ticker not in asset_rows]
    if missing_tickers:
        raise AppError(
            "Holding creation failed",
            "asset_not_found",
            f"Asset {', '.join(missing_tickers)} not found",
            404,
        )

    existing_result = await db.execute(
        select(holdings).where(holdings.c.portfolio_id == portfolio_id, holdings.c.ticker.in_(tickers))
    )
    existing_rows = {row["ticker"]: row for row in existing_result.mappings().all()}

    upserted_rows: list[dict] = []
    for ticker, bucket in normalized.items():
        quantity = float(bucket["quantity"])
        avg_buy_price = float(bucket["cost"]) / quantity
        buy_currency = str(bucket["buy_currency"])
        existing = existing_rows.get(ticker)

        if existing is None:
            statement = (
                insert(holdings)
                .values(
                    portfolio_id=portfolio_id,
                    ticker=ticker,
                    quantity=quantity,
                    avg_buy_price=avg_buy_price,
                    buy_currency=buy_currency,
                )
                .returning(holdings)
            )
        else:
            total_quantity = float(existing["quantity"]) + quantity
            weighted_avg_price = (
                float(existing["quantity"]) * float(existing["avg_buy_price"]) + (quantity * avg_buy_price)
            ) / total_quantity
            statement = (
                update(holdings)
                .where(holdings.c.id == existing["id"])
                .values(
                    quantity=total_quantity,
                    avg_buy_price=weighted_avg_price,
                    buy_currency=buy_currency,
                )
                .returning(holdings)
            )

        result = await db.execute(statement)
        upserted_rows.append(result.mappings().one())

    return [HoldingOut.model_validate(row) for row in upserted_rows]


def _merge_holdings_rows(rows: Iterable[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    order: list[str] = []

    for raw_row in rows:
        row = dict(raw_row)
        ticker = row["ticker"]
        quantity = float(row["quantity"])
        avg_buy_price = float(row["avg_buy_price"])
        buy_currency = str(row.get("buy_currency", "INR")).upper()

        if ticker not in merged:
            merged[ticker] = row
            merged[ticker]["quantity"] = quantity
            merged[ticker]["avg_buy_price"] = avg_buy_price
            merged[ticker]["buy_currency"] = buy_currency
            merged[ticker]["_cost_basis"] = quantity * avg_buy_price
            order.append(ticker)
            continue

        existing = merged[ticker]
        if str(existing.get("buy_currency", buy_currency)).upper() != buy_currency:
            raise AppError(
                "Holding creation failed",
                "currency_mismatch",
                f"Mixed currencies are not supported for {ticker}",
                400,
            )

        total_quantity = float(existing["quantity"]) + quantity
        total_cost = float(existing["_cost_basis"]) + quantity * avg_buy_price
        existing["quantity"] = total_quantity
        existing["avg_buy_price"] = total_cost / total_quantity if total_quantity else avg_buy_price
        existing["_cost_basis"] = total_cost
        existing["created_at"] = min(existing.get("created_at"), row.get("created_at")) if existing.get("created_at") and row.get("created_at") else existing.get("created_at") or row.get("created_at")
        existing["updated_at"] = max(existing.get("updated_at"), row.get("updated_at")) if existing.get("updated_at") and row.get("updated_at") else existing.get("updated_at") or row.get("updated_at")

    merged_rows = []
    for ticker in order:
        row = merged[ticker]
        row.pop("_cost_basis", None)
        merged_rows.append(row)
    return merged_rows
