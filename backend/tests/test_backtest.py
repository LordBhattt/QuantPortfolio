"""Tests for Backtest Lab: pure optimization, walk-forward engine, service and router."""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("cvxpy")

from backend.quant.backtest import _compute_metrics, run_backtest
from backend.quant.smart_backtest import SmartConfig, _hrp, select_config, smart_weights
from backend.schemas.backtest import BacktestRequest, BacktestResponse, StrategyMetrics
from backend.schemas.optimization import PortfolioConstraints
from backend.services.optimization_service import optimize_from_returns


def _create_synthetic_returns(n_days: int = 150, seed: int = 42) -> tuple[pd.DataFrame, list[str], list[str]]:
    np.random.seed(seed)
    tickers = ["RELIANCE.NS", "TCS.NS", "GOLDBEES.NS"]
    asset_classes = ["stock", "stock", "gold"]

    # Generate correlated daily returns
    cov = np.array([
        [0.0004, 0.0001, 0.00005],
        [0.0001, 0.0003, 0.00002],
        [0.00005, 0.00002, 0.00015],
    ])
    mean = np.array([0.0005, 0.0004, 0.0003])
    returns_data = np.random.multivariate_normal(mean, cov, size=n_days)

    dates = pd.date_range(end="2026-01-01", periods=n_days, freq="B")
    returns_df = pd.DataFrame(returns_data, index=dates, columns=tickers)
    return returns_df, tickers, asset_classes


def test_optimize_from_returns_pure() -> None:
    returns_df, tickers, asset_classes = _create_synthetic_returns()

    result = optimize_from_returns(
        returns_df=returns_df,
        tickers=tickers,
        asset_classes=asset_classes,
        constraints=None,
        risk_tolerance=0.5,
        use_regime=False,
        regime_detector=None,
        ml_forecasts=None,
        use_ml=False,
    )

    assert "weights" in result
    assert "regime_state" in result
    assert "expected_returns_annual" in result
    assert "cov_annual" in result

    weights = result["weights"]
    assert len(weights) == len(tickers)
    assert pytest.approx(sum(weights.values()), rel=1e-5) == 1.0
    for w in weights.values():
        assert w >= -1e-6
        assert w <= 1.0 + 1e-6


def test_optimize_from_returns_with_constraints_dict() -> None:
    returns_df, tickers, asset_classes = _create_synthetic_returns()

    constraints_dict = {
        "stocks": {"min": 0.2, "max": 0.6},
        "crypto": {"min": 0.0, "max": 0.1},
        "gold": {"min": 0.2, "max": 0.5},
        "mf_etf": {"min": 0.0, "max": 0.2},
        "bonds": {"min": 0.0, "max": 0.2},
    }

    result = optimize_from_returns(
        returns_df=returns_df,
        tickers=tickers,
        asset_classes=asset_classes,
        constraints=constraints_dict,
        risk_tolerance=0.5,
        use_regime=False,
        regime_detector=None,
        ml_forecasts=None,
        use_ml=False,
    )

    weights = result["weights"]
    stock_weight = weights["RELIANCE.NS"] + weights["TCS.NS"]
    gold_weight = weights["GOLDBEES.NS"]

    assert stock_weight >= 0.20 - 1e-4
    assert stock_weight <= 0.60 + 1e-4
    assert gold_weight >= 0.20 - 1e-4
    assert gold_weight <= 0.50 + 1e-4


def test_run_backtest_walk_forward() -> None:
    np.random.seed(42)
    n_days = 320
    dates = pd.date_range(start="2024-01-01", periods=n_days, freq="B")

    # Generate synthetic price series
    tickers = ["RELIANCE.NS", "TCS.NS"]
    asset_classes = ["stock", "stock"]

    p_rel = 2000.0 * np.exp(np.cumsum(np.random.normal(0.0005, 0.015, n_days)))
    p_tcs = 3000.0 * np.exp(np.cumsum(np.random.normal(0.0004, 0.012, n_days)))
    p_spy = 400.0 * np.exp(np.cumsum(np.random.normal(0.0003, 0.010, n_days)))
    p_nifty = 200.0 * np.exp(np.cumsum(np.random.normal(0.0004, 0.011, n_days)))

    prices = pd.DataFrame(
        {
            "RELIANCE.NS": p_rel,
            "TCS.NS": p_tcs,
            "SPY": p_spy,
            "NIFTYBEES.NS": p_nifty,
        },
        index=dates,
    )

    res = run_backtest(
        prices=prices,
        tickers=tickers,
        asset_classes=asset_classes,
        constraints=None,
        lookback_years=1,
        rebalance="monthly",
        risk_tolerance=0.5,
        cost_bps=10.0,
        use_ml=False,
        use_regime=False,
        regime_detector=None,
        forecaster=None,
        initial_value=100000.0,
    )

    assert "equity_curves" in res
    assert "metrics" in res
    assert "weights_history" in res
    assert "strategy_names" in res

    expected_strats = {"Optimized", "QP Smart", "Equal Weight", "Buy and Hold", "Min Variance", "SPY", "NIFTY"}
    assert set(res["strategy_names"]) == expected_strats

    for strat in expected_strats:
        assert strat in res["equity_curves"]
        assert strat in res["metrics"]
        m = res["metrics"][strat]
        assert "final_value" in m
        assert "total_profit_inr" in m
        assert "cagr" in m
        assert "volatility" in m
        assert "sharpe" in m
        assert "sortino" in m
        assert "max_drawdown" in m
        assert "calmar" in m
        assert "avg_turnover" in m
        assert m["max_drawdown"] <= 0.0001

    assert len(res["weights_history"]) > 0
    first_hist = res["weights_history"][0]
    assert "date" in first_hist
    assert "RELIANCE.NS" in first_hist
    assert "TCS.NS" in first_hist


def test_smart_config_selection_never_reads_after_split() -> None:
    dates = pd.date_range("2020-01-01", periods=100, freq="B")
    prices = pd.DataFrame({"AAA": np.linspace(100, 120, len(dates))}, index=dates)
    split_date = dates[59]
    seen: list[pd.Timestamp] = []

    def score(_: SmartConfig, train: pd.DataFrame) -> float:
        seen.append(train.index.max())
        return float(train["AAA"].iloc[-1])

    select_config(prices, split_date, score)
    assert seen
    assert all(date <= split_date for date in seen)


def test_hrp_produces_non_equal_weights_for_heterogeneous_assets() -> None:
    rng = np.random.default_rng(7)
    returns = pd.DataFrame(
        rng.normal(0.0, [0.01, 0.03, 0.06], size=(180, 3)),
        columns=["low", "medium", "high"],
    )
    weights = _hrp(returns)
    assert np.isclose(weights.sum(), 1.0)
    assert not np.allclose(weights, np.full(3, 1 / 3), atol=1e-3)


def test_no_trade_band_reduces_turnover() -> None:
    returns = pd.DataFrame(
        np.tile([[0.01, 0.002, 0.001]], (80, 1)),
        columns=["a", "b", "c"],
    )
    previous = {"a": 1 / 3, "b": 1 / 3, "c": 1 / 3}

    def optimizer(_: pd.DataFrame, names: list[str], __: list[str]) -> dict[str, float]:
        return {names[0]: 0.70, names[1]: 0.20, names[2]: 0.10}

    config = SmartConfig("No-trade", "optimizer", no_trade_band=0.15)
    bounded = smart_weights(
        returns, ["a", "b", "c"], ["stock", "stock", "gold"], None,
        config, optimizer, previous_weights=previous,
    )
    unconstrained_turnover = sum(abs(optimizer(returns, ["a", "b", "c"], [])[ticker] - previous[ticker]) for ticker in previous)
    bounded_turnover = sum(abs(bounded[ticker] - previous[ticker]) for ticker in previous)
    assert bounded_turnover < unconstrained_turnover


def test_compute_metrics_numerical_stability() -> None:
    dates = pd.date_range("2025-01-01", periods=100, freq="B")
    flat_equity = pd.Series([100000.0] * 100, index=dates)

    m = _compute_metrics(flat_equity, [0.0], 100000.0, 0.065)
    assert m["final_value"] == 100000.0
    assert m["total_profit_inr"] == 0.0
    assert m["cagr"] == 0.0
    assert m["volatility"] == 0.0
    assert m["sharpe"] == 0.0
    assert m["max_drawdown"] == 0.0


def test_backtest_schemas() -> None:
    req = BacktestRequest(portfolio_id="00000000-0000-0000-0000-000000000001")
    assert req.lookback_years == 3
    assert req.rebalance == "monthly"
    assert req.risk_tolerance == 0.5
    assert req.cost_bps == 10
    assert not req.use_ml
    assert not req.use_regime

    m = StrategyMetrics(
        name="Optimized",
        final_value=125000.0,
        total_profit_inr=25000.0,
        cagr=0.12,
        volatility=0.15,
        sharpe=0.8,
        sortino=1.1,
        max_drawdown=-0.08,
        calmar=1.5,
        avg_turnover=0.05,
    )
    assert m.name == "Optimized"
    assert m.total_profit_inr == 25000.0


def test_backtest_router_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from backend.data_types import CurrentUser
    from backend.cache.redis_cache import RedisCache
    import backend.routers.backtest as backtest_router
    import uuid

    fake_user = CurrentUser(id=uuid.uuid4(), email="tester@example.com", full_name="Tester", is_active=True)
    fake_cache = RedisCache()

    async def fake_run_backtest_service(request, db, fetcher, regime_detector, forecaster, user_id=None):
        return BacktestResponse(
            strategies=[
                StrategyMetrics(
                    name="Optimized",
                    final_value=120000.0,
                    total_profit_inr=20000.0,
                    cagr=0.10,
                    volatility=0.12,
                    sharpe=0.9,
                    sortino=1.2,
                    max_drawdown=-0.05,
                    calmar=2.0,
                    avg_turnover=0.03,
                ),
                StrategyMetrics(
                    name="Equal Weight",
                    final_value=115000.0,
                    total_profit_inr=15000.0,
                    cagr=0.08,
                    volatility=0.13,
                    sharpe=0.7,
                    sortino=1.0,
                    max_drawdown=-0.07,
                    calmar=1.1,
                    avg_turnover=0.04,
                ),
            ],
            equity_curves={"Optimized": [{"date": "2025-01-01", "value": 100000.0}]},
            drawdown_curves={"Optimized": [{"date": "2025-01-01", "drawdown": 0.0}]},
            weights_history=[{"date": "2025-01-01", "RELIANCE.NS": 0.5, "TCS.NS": 0.5}],
            best_strategy="Optimized",
            headline="Optimized beat Equal Weight by +INR 5,000 over 3Y",
            parameters={"portfolio_id": str(request.portfolio_id)},
        )

    monkeypatch.setattr(backtest_router, "run_backtest_service", fake_run_backtest_service)

    app = FastAPI()
    app.include_router(backtest_router.router)
    app.dependency_overrides[backtest_router.get_current_user] = lambda: fake_user
    app.dependency_overrides[backtest_router.get_db] = lambda: None
    app.dependency_overrides[backtest_router.get_fetcher] = lambda: None
    app.dependency_overrides[backtest_router.get_cache] = lambda: fake_cache

    client = TestClient(app)
    resp = client.post(
        "/api/v1/backtest/",
        json={"portfolio_id": "00000000-0000-0000-0000-000000000001", "lookback_years": 3},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["best_strategy"] == "Optimized"
    assert "Optimized beat Equal Weight" in data["headline"]
    assert len(data["strategies"]) == 2

    # Second request should come from cache!
    resp_cached = client.post(
        "/api/v1/backtest/",
        json={"portfolio_id": "00000000-0000-0000-0000-000000000001", "lookback_years": 3},
    )
    assert resp_cached.status_code == 200
    assert resp_cached.json()["best_strategy"] == "Optimized"
