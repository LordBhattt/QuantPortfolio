from __future__ import annotations

import uuid

import pandas as pd
import pytest

pytest.importorskip("pandas")

from sqlalchemy import insert

from backend.models.asset import AssetClass, assets
from backend.models.holding import holdings
from backend.models.portfolio import portfolios
from backend.models.user import users
from backend.services.analytics_service import get_portfolio_analytics


class FakeFetcher:
    async def get_usd_inr_rate(self) -> float:
        return 1.0

    async def get_latest_prices_in_inr(self, instruments: list[dict]) -> dict[str, float]:
        del instruments
        return {"TEST.NS": 103.0}

    async def get_price_history(self, ticker: str, source: str, days: int = 365):
        del ticker, source, days
        return pd.DataFrame(
            {"open": [99.0, 100.0], "high": [101.0, 102.0], "low": [98.0, 99.0], "close": [100.0, 101.0], "volume": [1000, 1200]},
            index=pd.date_range("2024-01-01", periods=2, freq="D"),
        )


@pytest.mark.asyncio
async def test_analytics_uses_live_quote_for_current_value_and_total_pnl(sqlite_session_factory) -> None:
    user_id = uuid.UUID("00000000-0000-0000-0000-000000000301")
    portfolio_id = uuid.UUID("00000000-0000-0000-0000-000000000401")

    async with sqlite_session_factory() as session:
        await session.execute(
            insert(users).values(
                id=user_id,
                email="analytics-live@example.com",
                hashed_password="hashed",
                full_name="Analytics User",
                is_active=True,
            )
        )
        await session.execute(
            insert(assets).values(
                ticker="TEST.NS",
                name="Test Equity",
                asset_class=AssetClass.STOCK,
                exchange="NSE",
                currency="INR",
                data_source="yahoo",
                is_active=True,
            )
        )
        await session.execute(
            insert(portfolios).values(
                id=portfolio_id,
                user_id=user_id,
                name="Live Quote Portfolio",
                description=None,
                base_currency="INR",
                constraints={},
            )
        )
        await session.execute(
            insert(holdings).values(
                portfolio_id=portfolio_id,
                ticker="TEST.NS",
                quantity=10,
                avg_buy_price=100,
                buy_currency="INR",
            )
        )
        await session.commit()

    async with sqlite_session_factory() as session:
        analytics = await get_portfolio_analytics(portfolio_id, user_id, session, FakeFetcher())

    assert analytics.total_invested_inr == 1000.0
    assert analytics.total_value_inr == 1030.0
    assert analytics.total_pnl_inr == 30.0
    assert analytics.day_pnl_inr == 20.0
    assert analytics.holdings_breakdown[0].current_price_inr == 103.0
