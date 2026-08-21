import pandas as pd
import pytest

from backend.quant.backtest import BacktestPeriod, StrategyResult
from backend.quant.backtest_stats import compute_metrics
from backend.quant.tax_aware_backtest import run_tax_aware_backtest, to_strategy_result


def _synthetic_price_frame(change_points: list[tuple[pd.Timestamp, float]], n_days: int = 500) -> pd.DataFrame:
    """A step-function price series: price holds at each value from its
    change point onward until the next one."""
    idx = pd.bdate_range(change_points[0][0], periods=n_days)
    price = pd.Series(index=idx, dtype=float)
    for change_date, value in change_points:
        price.loc[price.index >= change_date] = value
    return pd.DataFrame({"close": price})


def _build_strategy_result(periods_spec: list[tuple[pd.Timestamp, dict[str, float]]]) -> StrategyResult:
    periods = [
        BacktestPeriod(date=reb_date, regime="sideways", weights=weights, period_return=0.0, turnover=0.0)
        for reb_date, weights in periods_spec
    ]
    idx = pd.bdate_range(periods_spec[0][0], periods=500)
    daily_returns = pd.Series(0.0, index=idx)
    equity_curve = (1.0 + daily_returns).cumprod()
    return StrategyResult(name="full_pipeline", periods=periods, daily_returns=daily_returns, equity_curve=equity_curve)


def test_tax_aware_policy_pays_less_tax_than_fifo_across_multiple_rebalances() -> None:
    """A three-period walk: build a 50% BTC position, top it up to 100%
    (creating a second lot at a different cost basis), then trim back to
    30%. By the trim date, the OLDER lot (bought at 50,000) is sitting on
    a gain and the NEWER lot (bought at 80,000) is sitting on a loss --
    FIFO's age-only ordering sells the gain lot and pays real tax; the
    tax-aware policy finds the loss lot instead."""
    dates = [pd.Timestamp("2022-01-03"), pd.Timestamp("2022-06-01"), pd.Timestamp("2023-01-02")]
    price_frame = _synthetic_price_frame([(dates[0], 50_000.0), (dates[1], 80_000.0), (dates[2], 60_000.0)])
    price_data = {"BTC": price_frame}
    asset_classes = {"BTC": "crypto"}

    periods_spec = [
        (dates[0], {"BTC": 0.5}),
        (dates[1], {"BTC": 1.0}),
        (dates[2], {"BTC": 0.3}),
    ]
    strategy_result = _build_strategy_result(periods_spec)

    results = run_tax_aware_backtest(strategy_result, price_data, asset_classes, starting_capital=1_000_000.0)

    fifo_tax = results["fifo"].total_tax_paid
    aware_tax = results["tax_aware"].total_tax_paid

    assert fifo_tax > 0.0
    assert aware_tax < fifo_tax
    assert results["fifo"].tax_by_asset_class.get("crypto", 0.0) == pytest.approx(fifo_tax)

    no_tax_result = results["no_tax"]
    assert no_tax_result.total_tax_paid == pytest.approx(0.0)
    # same trade sizing/mechanics as fifo, just no tax subtracted -- so it
    # must end up worth at least as much as either taxed policy, isolating
    # tax as the only source of the difference.
    assert no_tax_result.equity_curve.iloc[-1] >= results["fifo"].equity_curve.iloc[-1]
    assert no_tax_result.equity_curve.iloc[-1] >= results["tax_aware"].equity_curve.iloc[-1]


def test_run_tax_aware_backtest_produces_valid_equity_curves() -> None:
    dates = [pd.Timestamp("2022-01-03"), pd.Timestamp("2022-06-01")]
    price_frame = _synthetic_price_frame([(dates[0], 100.0), (dates[1], 120.0)])
    price_data = {"AAA": price_frame}
    asset_classes = {"AAA": "stock"}
    periods_spec = [(dates[0], {"AAA": 1.0}), (dates[1], {"AAA": 1.0})]
    strategy_result = _build_strategy_result(periods_spec)

    results = run_tax_aware_backtest(strategy_result, price_data, asset_classes)

    for policy_result in results.values():
        assert (policy_result.equity_curve > 0).all()
        assert policy_result.equity_curve.index.is_monotonic_increasing


def test_to_strategy_result_wraps_cleanly_for_stats_reuse() -> None:
    dates = [pd.Timestamp("2022-01-03"), pd.Timestamp("2022-06-01")]
    price_frame = _synthetic_price_frame([(dates[0], 100.0), (dates[1], 120.0)])
    price_data = {"AAA": price_frame}
    asset_classes = {"AAA": "stock"}
    periods_spec = [(dates[0], {"AAA": 1.0}), (dates[1], {"AAA": 1.0})]
    strategy_result = _build_strategy_result(periods_spec)

    results = run_tax_aware_backtest(strategy_result, price_data, asset_classes)
    wrapped = to_strategy_result(results["fifo"], "fifo_after_tax")

    metrics = compute_metrics(wrapped)
    assert wrapped.name == "fifo_after_tax"
    assert metrics.n_observations == len(results["fifo"].daily_returns)


def test_raises_on_strategy_result_with_no_periods() -> None:
    empty = StrategyResult(name="empty", periods=[], daily_returns=pd.Series(dtype=float), equity_curve=pd.Series(dtype=float))
    with pytest.raises(ValueError):
        run_tax_aware_backtest(empty, {}, {})
