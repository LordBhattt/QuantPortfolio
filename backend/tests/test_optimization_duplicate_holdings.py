from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import pandas as pd
import pytest

pytest.importorskip("cvxpy")

from sqlalchemy import insert

from backend.models.asset import AssetClass, assets
from backend.models.holding import holdings
from backend.models.portfolio import portfolios
from backend.models.user import users
from backend.schemas.optimization import OptimizationRequest
from backend.services.optimization_service import run_optimization


class FakeFetcher:
    def __init__(self) -> None:
        dates = pd.date_range(datetime(2024, 1, 1), periods=300, freq="D")
        self.frames = {
            "BTC": pd.DataFrame({"close": [100 + index * 0.2 for index in range(300)]}, index=dates),
            "ETH": pd.DataFrame({"close": [50 + index * 0.1 for index in range(300)]}, index=dates),
        }

    async def get_price_history(self, ticker: str, source: str, days: int = 365):
        del source, days
        return self.frames[ticker]

    async def get_usd_inr_rate(self) -> float:
        return 80.0

    async def get_latest_prices_in_inr(self, instruments: list[dict]) -> dict[str, float]:
        return {item["ticker"]: float(self.frames[item["ticker"]]["close"].iloc[-1]) for item in instruments}


@pytest.mark.asyncio
async def test_run_optimization_handles_duplicate_holdings(sqlite_session_factory) -> None:
    user_id = uuid.uuid4()
    portfolio_id = uuid.uuid4()

    async with sqlite_session_factory() as session:
        await session.execute(
            insert(users).values(
                id=user_id,
                email="optimizer@example.com",
                hashed_password="hash",
                full_name="Optimizer",
                is_active=True,
            )
        )
        await session.execute(
            insert(portfolios).values(
                id=portfolio_id,
                user_id=user_id,
                name="Dupes Portfolio",
                description="Duplicate holdings",
                base_currency="INR",
                constraints={},
                last_optimized_weights=None,
                peak_value=None,
            )
        )
        await session.execute(
            insert(assets),
            [
                {
                    "ticker": "BTC",
                    "name": "Bitcoin",
                    "asset_class": AssetClass.CRYPTO,
                    "exchange": "CRYPTO",
                    "currency": "USD",
                    "data_source": "yahoo",
                    "is_active": True,
                },
                {
                    "ticker": "ETH",
                    "name": "Ethereum",
                    "asset_class": AssetClass.CRYPTO,
                    "exchange": "CRYPTO",
                    "currency": "USD",
                    "data_source": "yahoo",
                    "is_active": True,
                },
            ],
        )
        await session.execute(
            insert(holdings),
            [
                {
                    "portfolio_id": portfolio_id,
                    "ticker": "BTC",
                    "quantity": 0.5,
                    "avg_buy_price": 80.0,
                    "buy_currency": "USD",
                },
                {
                    "portfolio_id": portfolio_id,
                    "ticker": "BTC",
                    "quantity": 0.25,
                    "avg_buy_price": 100.0,
                    "buy_currency": "USD",
                },
                {
                    "portfolio_id": portfolio_id,
                    "ticker": "ETH",
                    "quantity": 1.0,
                    "avg_buy_price": 50.0,
                    "buy_currency": "USD",
                },
            ],
        )
        await session.commit()

    request = OptimizationRequest(portfolio_id=portfolio_id, risk_tolerance=0.5, use_regime_scaling=False, use_lstm_forecasts=False)
    async with sqlite_session_factory() as session:
        result = await run_optimization(request, user_id, session, FakeFetcher())

    assert len(result.optimal_weights) == 2
    assert {item.ticker for item in result.optimal_weights} == {"BTC", "ETH"}
