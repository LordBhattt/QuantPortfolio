from __future__ import annotations

import uuid
from types import SimpleNamespace
from uuid import UUID

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("jose")
pytest.importorskip("multipart")
pytest.importorskip("passlib")

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import insert, select

from backend.config import get_settings
from backend.database import get_db
from backend.models.asset import AssetClass, assets
from backend.models.holding import holdings
from backend.models.portfolio import portfolios
from backend.models.portfolio_alert import portfolio_alerts
from backend.routers import auth as auth_router
from backend.routers import portfolio as portfolio_router


settings = get_settings()


def _create_test_app(session_factory) -> FastAPI:
    app = FastAPI()
    app.include_router(auth_router.router)
    app.include_router(portfolio_router.router)

    async def override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = override_get_db
    return app


def _auth_headers(client: TestClient) -> dict[str, str]:
    token = client.cookies.get(settings.AUTH_COOKIE_NAME)
    assert token is not None
    return {"Cookie": f"{settings.AUTH_COOKIE_NAME}={token}"}


def _register_and_login(client: TestClient, email: str = "trader@example.com") -> None:
    password = "Password123!"

    register_response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Trader"},
    )
    assert register_response.status_code == 201
    assert register_response.json()["email"] == email
    assert register_response.json().get("access_token") is None
    assert client.cookies.get(settings.AUTH_COOKIE_NAME) is not None

    logout_response = client.post("/api/v1/auth/logout")
    assert logout_response.status_code == 204
    assert client.cookies.get(settings.AUTH_COOKIE_NAME) is None

    login_response = client.post(
        "/api/v1/auth/token",
        data={"username": email, "password": password},
    )
    assert login_response.status_code == 200
    assert login_response.json()["email"] == email
    assert login_response.json().get("access_token") is None
    assert client.cookies.get(settings.AUTH_COOKIE_NAME) is not None


@pytest.mark.asyncio
async def test_auth_flow_register_login_and_me(sqlite_session_factory) -> None:
    app = _create_test_app(sqlite_session_factory)
    client = TestClient(app)

    _register_and_login(client)

    me_response = client.get("/api/v1/auth/me", headers=_auth_headers(client))
    assert me_response.status_code == 200
    assert me_response.json()["email"] == "trader@example.com"


@pytest.mark.asyncio
async def test_holdings_crud_flow(sqlite_session_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    async with sqlite_session_factory() as session:
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

    app = _create_test_app(sqlite_session_factory)
    client = TestClient(app)
    _register_and_login(client, email="investor@example.com")

    calls: list[tuple[UUID, UUID]] = []

    async def fake_reoptimize(portfolio_id, user_id):
        calls.append((portfolio_id, user_id))

    monkeypatch.setattr(portfolio_router, "_reoptimize_portfolio_after_change", fake_reoptimize)

    portfolio_response = client.post(
        "/api/v1/portfolios/",
        json={"name": "Crypto Sleeve", "description": "Test portfolio", "base_currency": "USD"},
        headers=_auth_headers(client),
    )
    assert portfolio_response.status_code == 201
    portfolio_id = UUID(portfolio_response.json()["id"])

    holding_response = client.post(
        f"/api/v1/portfolios/{portfolio_id}/holdings",
        json={"ticker": "btc", "quantity": 2, "avg_buy_price": 10000, "buy_currency": "usd"},
        headers=_auth_headers(client),
    )
    assert holding_response.status_code == 201
    holding_id = holding_response.json()["id"]
    assert holding_response.json()["ticker"] == "BTC"

    list_response = client.get(
        f"/api/v1/portfolios/{portfolio_id}/holdings",
        headers=_auth_headers(client),
    )
    assert list_response.status_code == 200
    assert len(list_response.json()) == 1

    delete_response = client.delete(
        f"/api/v1/portfolios/{portfolio_id}/holdings/{holding_id}",
        headers=_auth_headers(client),
    )
    assert delete_response.status_code == 204

    empty_response = client.get(
        f"/api/v1/portfolios/{portfolio_id}/holdings",
        headers=_auth_headers(client),
    )
    assert empty_response.status_code == 200
    assert empty_response.json() == []
    assert len(calls) == 2


@pytest.mark.asyncio
async def test_background_reoptimization_updates_weights_and_alerts(sqlite_session_factory, monkeypatch: pytest.MonkeyPatch) -> None:
    async with sqlite_session_factory() as session:
        await session.execute(
            insert(assets),
            [
                {
                    "ticker": "RELIANCE.NS",
                    "name": "Reliance Industries",
                    "asset_class": AssetClass.STOCK,
                    "exchange": "NSE",
                    "currency": "INR",
                    "data_source": "yahoo",
                    "is_active": True,
                },
                {
                    "ticker": "LIQUIDBEES.NS",
                    "name": "Liquid BeES",
                    "asset_class": AssetClass.BOND,
                    "exchange": "NSE",
                    "currency": "INR",
                    "data_source": "yahoo",
                    "is_active": True,
                },
            ],
        )
        await session.commit()

    user_id = uuid.uuid4()
    portfolio_id = uuid.uuid4()

    async with sqlite_session_factory() as session:
        await session.execute(
            insert(portfolios).values(
                id=portfolio_id,
                user_id=user_id,
                name="Reopt Portfolio",
                description="Test portfolio",
                base_currency="INR",
                constraints={},
                last_optimized_weights=None,
                peak_value=None,
            )
        )
        await session.execute(
            insert(holdings).values(
                portfolio_id=portfolio_id,
                ticker="RELIANCE.NS",
                quantity=1,
                avg_buy_price=100,
                buy_currency="INR",
            )
        )
        await session.commit()

    calls: list[str] = []

    async def fake_sleep(_: float) -> None:
        return None

    async def fake_run_optimization(request, user_id, db, fetcher):
        del user_id, db, fetcher
        calls.append(str(request.portfolio_id))
        assert request.risk_tolerance == 0.5
        assert request.use_regime_scaling is True
        assert request.use_lstm_forecasts is False
        return SimpleNamespace(
            optimal_weights=[
                SimpleNamespace(asset_class="stock", weight=0.8, current_value_usd=100.0),
                SimpleNamespace(asset_class="bond", weight=0.2, current_value_usd=0.0),
            ]
        )

    monkeypatch.setattr(portfolio_router.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(portfolio_router, "run_optimization", fake_run_optimization)
    monkeypatch.setattr(portfolio_router, "get_fetcher", lambda: object())
    monkeypatch.setattr(portfolio_router, "AsyncSessionLocal", sqlite_session_factory)

    await portfolio_router._reoptimize_portfolio_after_change(portfolio_id, user_id)
    await portfolio_router._reoptimize_portfolio_after_change(portfolio_id, user_id)

    assert len(calls) == 2

    async with sqlite_session_factory() as session:
        portfolio_row = await session.execute(select(portfolios).where(portfolios.c.id == portfolio_id))
        stored_weights = portfolio_row.mappings().one()["last_optimized_weights"]
        assert stored_weights == {"stock": 0.8, "bond": 0.2}

        alert_rows = await session.execute(
            select(portfolio_alerts).where(
                portfolio_alerts.c.portfolio_id == portfolio_id,
                portfolio_alerts.c.alert_type == "post_addition_drift",
            )
        )
        assert len(alert_rows.mappings().all()) == 2