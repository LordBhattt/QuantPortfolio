import uuid

import pytest

pytest.importorskip("sqlalchemy")
pytest.importorskip("jose")
pytest.importorskip("passlib")
pytest.importorskip("redis")
pytest.importorskip("multipart")
pytest.importorskip("cvxpy")

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.data_types import CurrentUser
from backend.errors import AppError
from backend.schemas.backtest import BacktestResponse
import backend.routers.backtest as backtest_router


@pytest.fixture
def current_user() -> CurrentUser:
    return CurrentUser(id=uuid.uuid4(), email="user@example.com", full_name="Test User", is_active=True)


def _fake_response() -> BacktestResponse:
    return BacktestResponse(
        universe=["AAPL", "SPY"],
        lookback_days=504,
        transaction_cost_bps=10.0,
        baseline="equal_weight",
        data_through="2026-08-01",
        strategies=[],
        significance_vs_baseline=[],
        bandit_posterior=[],
    )


def test_get_backtest_route_returns_service_payload(monkeypatch: pytest.MonkeyPatch, current_user: CurrentUser) -> None:
    captured: dict = {}

    async def fake_run_backtest(lookback_days, transaction_cost_bps, baseline):
        captured["lookback_days"] = lookback_days
        captured["transaction_cost_bps"] = transaction_cost_bps
        captured["baseline"] = baseline
        return _fake_response()

    app = FastAPI()
    app.include_router(backtest_router.router)
    app.dependency_overrides[backtest_router.get_current_user] = lambda: current_user
    monkeypatch.setattr(backtest_router, "run_backtest", fake_run_backtest)

    client = TestClient(app)
    response = client.get("/api/v1/backtest/?lookback_days=252&transaction_cost_bps=5&baseline=equal_weight")

    assert response.status_code == 200
    payload = response.json()
    assert payload["universe"] == ["AAPL", "SPY"]
    assert captured == {"lookback_days": 252, "transaction_cost_bps": 5.0, "baseline": "equal_weight"}


def test_get_backtest_route_requires_authentication() -> None:
    app = FastAPI()
    app.include_router(backtest_router.router)

    client = TestClient(app)
    with pytest.raises(AppError) as exc_info:
        client.get("/api/v1/backtest/")

    assert exc_info.value.status_code == 401
