from __future__ import annotations

import uuid

import pandas as pd
import pytest

pytest.importorskip("pandas")
pytest.importorskip("apscheduler")

from sqlalchemy import insert, select

from backend.models.asset import AssetClass, assets
from backend.models.holding import holdings
from backend.models.portfolio import portfolios
from backend.models.portfolio_alert import portfolio_alerts
from backend.models.user import users
from backend.quant.regime import RegimeDetector
from backend.services.portfolio_monitor import monitor_all_active_portfolios
from backend.tasks.scheduler import create_scheduler


class FakeCache:
    async def invalidate_pattern(self, pattern: str) -> None:
        del pattern


class FakeFetcher:
    def __init__(self) -> None:
        self.cache = FakeCache()

    async def get_usd_inr_rate(self) -> float:
        return 1.0

    async def get_price_history(self, ticker: str, source: str, days: int = 5):
        del source, days
        prices = {
            "LIQUIDBEES.NS": [100.0, 100.0],
            "RELIANCE.NS": [1000.0, 1000.0],
        }
        frame = pd.DataFrame({"close": prices[ticker]}, index=pd.date_range("2024-01-01", periods=2, freq="D"))
        return frame


class FakeRegimeDetector:
    def fit(self, returns):
        del returns


@pytest.mark.asyncio
async def test_monitor_all_active_portfolios_persists_alert(sqlite_session_factory) -> None:
    async with sqlite_session_factory() as session:
        await session.execute(
            insert(users).values(
                id=uuid.UUID("00000000-0000-0000-0000-000000000101"),
                email="monitor@example.com",
                hashed_password="hashed",
                full_name="Monitor User",
                is_active=True,
            )
        )
        await session.execute(
            insert(assets),
            [
                {
                    "ticker": "LIQUIDBEES.NS",
                    "name": "Liquid BeES",
                    "asset_class": AssetClass.BOND,
                    "exchange": "NSE",
                    "currency": "INR",
                    "data_source": "yahoo",
                    "is_active": True,
                },
                {
                    "ticker": "RELIANCE.NS",
                    "name": "Reliance Industries",
                    "asset_class": AssetClass.STOCK,
                    "exchange": "NSE",
                    "currency": "INR",
                    "data_source": "yahoo",
                    "is_active": True,
                },
            ],
        )
        await session.execute(
            insert(portfolios).values(
                id=uuid.UUID("00000000-0000-0000-0000-000000000201"),
                user_id=uuid.UUID("00000000-0000-0000-0000-000000000101"),
                name="Monitor Portfolio",
                description=None,
                base_currency="INR",
                constraints={},
                last_optimized_weights={"bond": 0.8, "stock": 0.2},
                peak_value=19000,
            )
        )
        await session.execute(
            insert(portfolios).values(
                id=uuid.UUID("00000000-0000-0000-0000-000000000202"),
                user_id=uuid.UUID("00000000-0000-0000-0000-000000000101"),
                name="Quiet Portfolio",
                description=None,
                base_currency="INR",
                constraints={},
                last_optimized_weights={"bond": 0.5, "stock": 0.5},
                peak_value=20000,
            )
        )
        await session.execute(
            insert(holdings),
            [
                {
                    "portfolio_id": uuid.UUID("00000000-0000-0000-0000-000000000201"),
                    "ticker": "LIQUIDBEES.NS",
                    "quantity": 100,
                    "avg_buy_price": 100,
                    "buy_currency": "INR",
                },
                {
                    "portfolio_id": uuid.UUID("00000000-0000-0000-0000-000000000201"),
                    "ticker": "RELIANCE.NS",
                    "quantity": 10,
                    "avg_buy_price": 1000,
                    "buy_currency": "INR",
                },
            ],
        )
        await session.commit()

    async with sqlite_session_factory() as session:
        alerts = await monitor_all_active_portfolios(session, FakeFetcher(), persist_alerts=True)
        await session.commit()

    assert len(alerts) == 1
    assert alerts[0].recommended_action == "rebalance"
    assert len(alerts[0].drifted_assets) == 2

    async with sqlite_session_factory() as session:
        result = await session.execute(select(portfolio_alerts))
        rows = result.mappings().all()

    assert len(rows) == 1
    assert rows[0]["alert_type"] == "rebalance"


def test_scheduler_registers_monitor_jobs() -> None:
    scheduler = create_scheduler(FakeRegimeDetector(), FakeFetcher())
    job_names = {job.name for job in scheduler.get_jobs()}

    assert "portfolio_monitor_market_hours" in job_names
    assert "portfolio_monitor_eod" in job_names