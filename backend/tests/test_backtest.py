import numpy as np
import pandas as pd
import pytest

pytest.importorskip("cvxpy")

from backend.quant.backtest import (
    STRATEGIES,
    _lookback_window,
    _monthly_rebalance_dates,
    run_walk_forward_backtest,
)


def _synthetic_returns(n_days: int = 1100, n_assets: int = 4, seed: int = 7) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-01", periods=n_days)
    tickers = [f"ASSET_{i}" for i in range(n_assets)]
    means = rng.uniform(0.0002, 0.0008, size=n_assets)
    vols = rng.uniform(0.008, 0.02, size=n_assets)
    data = rng.normal(loc=means, scale=vols, size=(n_days, n_assets))
    return pd.DataFrame(data, index=dates, columns=tickers)


def test_monthly_rebalance_dates_returns_first_trading_day_each_month() -> None:
    dates = pd.bdate_range("2021-01-01", periods=90)
    rebalance_dates = _monthly_rebalance_dates(dates)
    periods = {date.to_period("M") for date in rebalance_dates}
    assert len(rebalance_dates) == len(periods)
    for period in periods:
        first_of_month = min(date for date in dates if date.to_period("M") == period)
        assert first_of_month in rebalance_dates


def test_lookback_window_excludes_the_rebalance_date_itself() -> None:
    returns_df = _synthetic_returns(n_days=50, n_assets=2)
    reb_date = returns_df.index[30]
    window = _lookback_window(returns_df, reb_date, lookback_days=10)
    assert reb_date not in window.index
    assert len(window) == 10
    assert window.index.max() == returns_df.index[29]


def test_walk_forward_backtest_runs_all_strategies_without_lookahead() -> None:
    returns_df = _synthetic_returns(n_days=1100, n_assets=4)
    asset_classes = {ticker: "stock" for ticker in returns_df.columns}

    results = run_walk_forward_backtest(
        returns_df,
        asset_classes,
        lookback_days=252,
        transaction_cost_bps=10.0,
    )

    assert set(results.keys()) == set(STRATEGIES.keys())
    for result in results.values():
        assert len(result.periods) > 0
        assert (result.equity_curve > 0).all()
        for period in result.periods:
            assert pytest.approx(sum(period.weights.values()), rel=1e-6) == 1.0
            assert all(weight >= -1e-9 for weight in period.weights.values())


def test_transaction_costs_reduce_first_period_return() -> None:
    returns_df = _synthetic_returns(n_days=400, n_assets=3)
    asset_classes = {ticker: "stock" for ticker in returns_df.columns}
    strategies = {"equal_weight": STRATEGIES["equal_weight"]}

    cheap = run_walk_forward_backtest(returns_df, asset_classes, strategies, lookback_days=252, transaction_cost_bps=0.0)
    expensive = run_walk_forward_backtest(returns_df, asset_classes, strategies, lookback_days=252, transaction_cost_bps=500.0)

    cheap_first_return = cheap["equal_weight"].periods[0].period_return
    expensive_first_return = expensive["equal_weight"].periods[0].period_return
    assert expensive_first_return < cheap_first_return


def test_insufficient_history_raises() -> None:
    returns_df = _synthetic_returns(n_days=50, n_assets=2)
    asset_classes = {ticker: "stock" for ticker in returns_df.columns}
    with pytest.raises(ValueError):
        run_walk_forward_backtest(returns_df, asset_classes, lookback_days=252)
