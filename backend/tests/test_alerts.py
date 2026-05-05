from __future__ import annotations

import uuid

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import insert, select

from backend.data_types import CurrentUser
from backend.database import get_db
from backend.models.asset import AssetClass, assets
from backend.models.holding import holdings
from backend.models.portfolio import portfolios
from backend.models.portfolio_alert import portfolio_alerts
from backend.models.user import users
from backend.routers import alerts as alerts_router


def _create_test_app(session_factory, user_id: uuid.UUID) -> FastAPI:
    app = FastAPI()
    app.include_router(alerts_router.router)

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[alerts_router.get_current_user] = lambda: CurrentUser(
        id=user_id,
        email="alerts@example.com",
        full_name="Alerts User",
        is_active=True,
    )
    return app


@pytest.mark.asyncio
async def test_alerts_lifecycle(sqlite_session_factory) -> None:
    user_id = uuid.uuid4()
    portfolio_id = uuid.uuid4()
    alert_id = uuid.uuid4()

    async with sqlite_session_factory() as session:
        await session.execute(
            insert(users).values(
                id=user_id,
                email="alerts@example.com",
                hashed_password="hashed",
                full_name="Alerts User",
                is_active=True,
            )
        )
        await session.execute(
            insert(portfolios).values(
                id=portfolio_id,
                user_id=user_id,
                name="Alert Portfolio",
                description=None,
                base_currency="INR",
                constraints={},
                last_optimized_weights={"stock": 0.6, "bond": 0.4},
                peak_value=1000,
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
            insert(holdings),
            [
                {
                    "portfolio_id": portfolio_id,
                    "ticker": "LIQUIDBEES.NS",
                    "quantity": 10,
                    "avg_buy_price": 100,
                    "buy_currency": "INR",
                },
                {
                    "portfolio_id": portfolio_id,
                    "ticker": "RELIANCE.NS",
                    "quantity": 1,
                    "avg_buy_price": 100,
                    "buy_currency": "INR",
                },
            ],
        )
        await session.execute(
            insert(portfolio_alerts).values(
                id=alert_id,
                portfolio_id=portfolio_id,
                alert_type="rebalance",
                message="Please rebalance",
                is_read=False,
            )
        )
        await session.commit()

    app = _create_test_app(sqlite_session_factory, user_id)
    client = TestClient(app)

    list_response = client.get("/api/v1/alerts/")
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1
    assert list_response.json()[0]["message"] == "Please rebalance"

    read_response = client.patch(f"/api/v1/alerts/{alert_id}/read")
    assert read_response.status_code == 204

    read_all_response = client.patch("/api/v1/alerts/read-all")
    assert read_all_response.status_code == 204

    async with sqlite_session_factory() as session:
        remaining = await session.execute(select(portfolio_alerts).where(portfolio_alerts.c.is_read.is_(False)))
        assert remaining.mappings().all() == []