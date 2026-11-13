import uuid
import numpy as np
import pandas as pd
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.data_types import CurrentUser
from backend.quant.stress import (
    HISTORICAL_SCENARIOS,
    PROXY_MAP,
    HoldingImpact,
    ScenarioResult,
    compute_custom_shock,
    compute_historical_scenario,
)
from backend.schemas.stress import (
    CustomShockRequest,
    HoldingImpactOut,
    ScenarioResultOut,
    StressTestResponse,
)
import backend.routers.risk as risk_router


def _make_price_df(start: str, end: str, start_price: float, end_price: float) -> pd.DataFrame:
    dates = pd.date_range(start, end, freq="B")
    if len(dates) < 2:
        dates = pd.date_range(start, periods=2, freq="D")
    prices = np.linspace(start_price, end_price, len(dates))
    return pd.DataFrame({"close": prices}, index=dates)


def test_compute_historical_scenario_direct_data() -> None:
    scenario = {
        "name": "COVID",
        "label": "COVID Crash",
        "start": "2020-02-19",
        "end": "2020-03-23",
    }
    holdings = [
        {"ticker": "AAPL", "weight": 0.6, "asset_class": "stock", "value_inr": 60000.0},
        {"ticker": "MSFT", "weight": 0.4, "asset_class": "stock", "value_inr": 40000.0},
    ]
    # AAPL drops 30% (100 -> 70), MSFT drops 20% (200 -> 160)
    price_data = {
        "AAPL": _make_price_df("2020-02-19", "2020-03-23", 100.0, 70.0),
        "MSFT": _make_price_df("2020-02-19", "2020-03-23", 200.0, 160.0),
    }

    result = compute_historical_scenario(
        scenario=scenario,
        holdings=holdings,
        price_data=price_data,
        portfolio_value_inr=100000.0,
    )

    assert result.scenario_name == "COVID"
    assert result.scenario_label == "COVID Crash"
    assert len(result.per_holding) == 2

    # AAPL: -30%, weight 0.6 -> -18%
    # MSFT: -20%, weight 0.4 -> -8%
    # Portfolio return: -26%
    assert pytest.approx(result.portfolio_return_pct, 0.01) == -26.0
    assert pytest.approx(result.portfolio_inr_impact, 0.01) == -26000.0
    assert result.per_holding[0].is_proxy is False
    assert result.per_holding[0].proxy_ticker is None


def test_compute_historical_scenario_proxy_fallback() -> None:
    scenario = {
        "name": "GFC",
        "label": "Global Financial Crisis",
        "start": "2008-09-01",
        "end": "2009-03-09",
    }
    # A new stock without 2008 data, plus crypto which didn't exist in 2008
    holdings = [
        {"ticker": "NEW_STOCK", "weight": 0.5, "asset_class": "stock", "value_inr": 50000.0},
        {"ticker": "BTC", "weight": 0.5, "asset_class": "crypto", "value_inr": 50000.0},
    ]
    # SPY was down ~50% in GFC. BTC-USD had no data in 2008.
    price_data = {
        "SPY": _make_price_df("2008-09-01", "2009-03-09", 100.0, 50.0),
        # BTC-USD absent
    }

    result = compute_historical_scenario(
        scenario=scenario,
        holdings=holdings,
        price_data=price_data,
        portfolio_value_inr=100000.0,
    )

    assert len(result.per_holding) == 2

    # NEW_STOCK falls back to SPY (-50%)
    h0 = result.per_holding[0]
    assert h0.ticker == "NEW_STOCK"
    assert h0.is_proxy is True
    assert h0.proxy_ticker == "SPY"
    assert pytest.approx(h0.scenario_return_pct, 0.01) == -50.0

    # BTC falls back to BTC-USD proxy which has no data -> 0.0%
    h1 = result.per_holding[1]
    assert h1.ticker == "BTC"
    assert h1.is_proxy is True
    assert h1.proxy_ticker == "BTC-USD"
    assert h1.scenario_return_pct == 0.0

    # Total: 0.5 * (-50%) + 0.5 * 0% = -25%
    assert pytest.approx(result.portfolio_return_pct, 0.01) == -25.0
    assert pytest.approx(result.portfolio_inr_impact, 0.01) == -25000.0


def test_compute_historical_scenario_ignores_non_finite_prices() -> None:
    scenario = {
        "name": "COVID",
        "label": "COVID Crash",
        "start": "2020-02-19",
        "end": "2020-03-23",
    }
    prices = _make_price_df("2020-02-19", "2020-03-23", 100.0, 80.0)
    prices.iloc[0, 0] = np.nan
    prices.iloc[2, 0] = np.inf

    result = compute_historical_scenario(
        scenario=scenario,
        holdings=[{"ticker": "AAPL", "weight": 1.0, "asset_class": "stock", "value_inr": 100000.0}],
        price_data={"AAPL": prices},
        portfolio_value_inr=100000.0,
    )

    assert np.isfinite(result.portfolio_return_pct)
    assert result.portfolio_return_pct < 0


def test_compute_custom_shock() -> None:
    holdings = [
        {"ticker": "INFY.NS", "weight": 0.5, "asset_class": "stock", "currency": "INR"},
        {"ticker": "AAPL", "weight": 0.3, "asset_class": "stock", "currency": "USD"},
        {"ticker": "BTC", "weight": 0.2, "asset_class": "crypto", "currency": "USD"},
    ]

    # Equities -10%, Crypto -20%, INR depreciates by 5% (+5% for USD assets)
    res = compute_custom_shock(
        holdings=holdings,
        portfolio_value_inr=100000.0,
        equities_pct=-10.0,
        crypto_pct=-20.0,
        gold_pct=0.0,
        bonds_pct=0.0,
        inr_move_pct=5.0,
    )

    # INFY.NS: -10% + 0% = -10%. Contrib = 0.5 * -10 = -5%
    # AAPL: -10% + 5% = -5%. Contrib = 0.3 * -5 = -1.5%
    # BTC: -20% + 5% = -15%. Contrib = 0.2 * -15 = -3.0%
    # Total return: -5 + -1.5 + -3.0 = -9.5%
    assert pytest.approx(res["portfolio_return_pct"], 0.01) == -9.5
    assert pytest.approx(res["portfolio_inr_impact"], 0.01) == -9500.0
    assert len(res["per_holding"]) == 3
    assert pytest.approx(res["per_holding"][0]["shock_pct"], 0.01) == -10.0
    assert pytest.approx(res["per_holding"][1]["shock_pct"], 0.01) == -5.0
    assert pytest.approx(res["per_holding"][2]["shock_pct"], 0.01) == -15.0


def test_stress_endpoints() -> None:
    portfolio_id = uuid.uuid4()
    user = CurrentUser(
        id=uuid.uuid4(),
        email="test@example.com",
        full_name="Tester",
        is_active=True,
    )

    app = FastAPI()
    app.include_router(risk_router.router)
    app.dependency_overrides[risk_router.get_current_user] = lambda: user
    app.dependency_overrides[risk_router.get_db] = lambda: None
    app.dependency_overrides[risk_router.get_fetcher] = lambda: None

    async def fake_run_stress_test(portfolio_id, user_id, db, fetcher):
        return StressTestResponse(
            portfolio_value_inr=150000.0,
            historical_scenarios=[
                ScenarioResultOut(
                    scenario_name="COVID",
                    scenario_label="COVID Crash",
                    scenario_start="2020-02-19",
                    scenario_end="2020-03-23",
                    portfolio_return_pct=-22.5,
                    portfolio_inr_impact=-33750.0,
                    per_holding=[
                        HoldingImpactOut(
                            ticker="AAPL",
                            asset_class="stock",
                            weight=1.0,
                            scenario_return_pct=-22.5,
                            portfolio_contribution_pct=-22.5,
                            is_proxy=False,
                            proxy_ticker=None,
                        )
                    ],
                )
            ],
            custom_shock=None,
        )

    async def fake_run_custom_stress(portfolio_id, user_id, db, fetcher, shock):
        return {
            "portfolio_return_pct": -5.0,
            "portfolio_inr_impact": -7500.0,
            "portfolio_value_inr": 150000.0,
            "per_holding": [],
        }

    risk_router.run_stress_test = fake_run_stress_test
    risk_router.run_custom_stress = fake_run_custom_stress

    client = TestClient(app)

    # 1. Historical stress endpoint
    resp1 = client.get(f"/api/v1/risk/{portfolio_id}/stress")
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["portfolio_value_inr"] == 150000.0
    assert len(data1["historical_scenarios"]) == 1
    assert data1["historical_scenarios"][0]["scenario_name"] == "COVID"

    # 2. Custom shock endpoint
    resp2 = client.post(
        f"/api/v1/risk/{portfolio_id}/stress/custom",
        json={"equities_pct": -10.0, "crypto_pct": -20.0},
    )
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["portfolio_return_pct"] == -5.0
    assert data2["portfolio_inr_impact"] == -7500.0
