from __future__ import annotations

import uuid

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("jose")
pytest.importorskip("multipart")
pytest.importorskip("passlib")

from sqlalchemy import insert, select

from backend.models.asset import AssetClass, assets
from backend.models.holding import holdings
from backend.models.portfolio import portfolios
from backend.models.user import users
from backend.schemas.portfolio import HoldingCreate
from backend.services.portfolio_service import add_holdings


@pytest.mark.asyncio
async def test_add_holdings_merges_duplicate_tickers(sqlite_session_factory) -> None:
    user_id = uuid.uuid4()
    portfolio_id = uuid.uuid4()

    async with sqlite_session_factory() as session:
        await session.execute(
            insert(users).values(
                id=user_id,
                email="merge@example.com",
                hashed_password="hash",
                full_name="Merge Test",
                is_active=True,
            )
        )
        await session.execute(
            insert(portfolios).values(
                id=portfolio_id,
                user_id=user_id,
                name="Merge Portfolio",
                description="Test",
                base_currency="INR",
                constraints={},
                last_optimized_weights=None,
                peak_value=None,
            )
        )
        await session.execute(
            insert(assets).values(
                ticker="BTC",
                name="Bitcoin",
                asset_class=AssetClass.CRYPTO,
                exchange="CRYPTO",
                currency="USD",
                data_source="coingecko",
                is_active=True,
            )
        )
        await session.commit()

    async with sqlite_session_factory() as session:
        created = await add_holdings(
            [
                HoldingCreate(ticker="BTC", quantity=0.5, avg_buy_price=100.0, buy_currency="INR"),
                HoldingCreate(ticker="btc", quantity=0.25, avg_buy_price=200.0, buy_currency="inr"),
            ],
            portfolio_id,
            user_id,
            session,
        )
        await session.commit()

    assert len(created) == 1
    assert created[0].ticker == "BTC"
    assert created[0].quantity == pytest.approx(0.75)

    async with sqlite_session_factory() as session:
        result = await session.execute(select(holdings).where(holdings.c.portfolio_id == portfolio_id))
        rows = result.mappings().all()

    assert len(rows) == 1
    assert rows[0]["quantity"] == pytest.approx(0.75)