import uuid

import pytest


pytest.importorskip("sqlalchemy")
pytest.importorskip("jose")
pytest.importorskip("passlib")
pytest.importorskip("redis")
pytest.importorskip("multipart")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.data_types import CurrentUser
from backend.schemas.asset import AssetOut
import backend.routers.assets as assets_router


@pytest.fixture
def current_user() -> CurrentUser:
    return CurrentUser(
        id=uuid.uuid4(),
        email="user@example.com",
        full_name="Test User",
        is_active=True,
    )


def test_assets_list_route_uses_alias_class(monkeypatch: pytest.MonkeyPatch, current_user: CurrentUser) -> None:
    async def fake_list_assets(db, q=None, asset_class=None, active_only=True):
        assert q == "REL"
        assert asset_class == "stock"
        assert active_only is True
        return [
            AssetOut(
                ticker="RELIANCE.NS",
                name="Reliance Industries",
                asset_class="stock",
                exchange="NSE",
                currency="INR",
                data_source="yahoo",
                is_active=True,
            )
        ]

    app = FastAPI()
    app.include_router(assets_router.router)
    app.dependency_overrides[assets_router.get_current_user] = lambda: current_user
    app.dependency_overrides[assets_router.get_db] = lambda: None
    monkeypatch.setattr(assets_router, "list_assets", fake_list_assets)

    client = TestClient(app)
    response = client.get("/api/v1/assets/?q=REL&class=stock")

    assert response.status_code == 200
    payload = response.json()
    assert payload[0]["ticker"] == "RELIANCE.NS"


def test_assets_get_route_returns_typed_payload(monkeypatch: pytest.MonkeyPatch, current_user: CurrentUser) -> None:
    async def fake_get_asset(ticker, db):
        assert ticker == "BTC"
        return AssetOut(
            ticker="BTC",
            name="Bitcoin",
            asset_class="crypto",
            exchange="CRYPTO",
            currency="USD",
            data_source="coingecko",
            is_active=True,
        )

    app = FastAPI()
    app.include_router(assets_router.router)
    app.dependency_overrides[assets_router.get_current_user] = lambda: current_user
    app.dependency_overrides[assets_router.get_db] = lambda: None
    monkeypatch.setattr(assets_router, "get_asset", fake_get_asset)

    client = TestClient(app)
    response = client.get("/api/v1/assets/BTC")

    assert response.status_code == 200
    assert response.json()["name"] == "Bitcoin"
