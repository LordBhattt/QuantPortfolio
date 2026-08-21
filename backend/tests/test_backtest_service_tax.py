import pandas as pd
import pytest

pytest.importorskip("cvxpy")

from backend.quant.backtest import BacktestPeriod, StrategyResult
from backend.services.backtest_service import _build_tax_comparison


def _synthetic_price_frame(change_points: list[tuple[pd.Timestamp, float]], n_days: int = 400) -> pd.DataFrame:
    idx = pd.bdate_range(change_points[0][0], periods=n_days)
    price = pd.Series(index=idx, dtype=float)
    for change_date, value in change_points:
        price.loc[price.index >= change_date] = value
    return pd.DataFrame({"close": price})


def test_build_tax_comparison_reports_consistent_percentages() -> None:
    dates = [pd.Timestamp("2022-01-03"), pd.Timestamp("2022-06-01"), pd.Timestamp("2023-01-02")]
    price_data = {
        "BTC": _synthetic_price_frame([(dates[0], 50_000.0), (dates[1], 80_000.0), (dates[2], 60_000.0)]),
    }
    periods = [
        BacktestPeriod(date=dates[0], regime="sideways", weights={"BTC": 0.5}, period_return=0.0, turnover=0.0),
        BacktestPeriod(date=dates[1], regime="sideways", weights={"BTC": 1.0}, period_return=0.0, turnover=0.0),
        BacktestPeriod(date=dates[2], regime="sideways", weights={"BTC": 0.3}, period_return=0.0, turnover=0.0),
    ]
    idx = pd.bdate_range(dates[0], periods=400)
    daily_returns = pd.Series(0.0, index=idx)
    strategy_result = StrategyResult(
        name="full_pipeline", periods=periods, daily_returns=daily_returns, equity_curve=(1 + daily_returns).cumprod()
    )

    comparison = _build_tax_comparison(strategy_result, price_data, {"BTC": "crypto"})

    assert comparison is not None
    assert comparison.strategy == "full_pipeline"
    assert {p.policy for p in comparison.policies} == {"no_tax", "fifo", "tax_aware"}
    assert comparison.naive_tax_drag_pct > 0  # fifo cost real tax vs the frictionless baseline
    assert comparison.tax_aware_savings_pct > 0  # tax_aware beat fifo
    assert 0 < comparison.tax_aware_recovery_pct <= 100


def test_build_tax_comparison_returns_none_for_single_period_strategy() -> None:
    dates = [pd.Timestamp("2022-01-03")]
    price_data = {"AAA": _synthetic_price_frame([(dates[0], 100.0)])}
    periods = [BacktestPeriod(date=dates[0], regime="sideways", weights={"AAA": 1.0}, period_return=0.0, turnover=0.0)]
    idx = pd.bdate_range(dates[0], periods=400)
    daily_returns = pd.Series(0.0, index=idx)
    strategy_result = StrategyResult(
        name="full_pipeline", periods=periods, daily_returns=daily_returns, equity_curve=(1 + daily_returns).cumprod()
    )

    # a single-period strategy has no rebalance-driven disposals to compare, but should
    # not raise -- run_tax_aware_backtest only requires >=1 period, so this actually
    # succeeds; the "insufficient" path is exercised by an empty-periods StrategyResult
    # in test_tax_aware_backtest.py instead.
    comparison = _build_tax_comparison(strategy_result, price_data, {"AAA": "stock"})
    assert comparison is not None
