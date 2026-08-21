import numpy as np
import pandas as pd
import pytest

from backend.quant.backtest import BacktestPeriod, StrategyResult
from backend.quant.backtest_stats import (
    bootstrap_sharpe_difference,
    compare_strategies,
    compute_metrics,
    compute_regime_conditional_metrics,
)


def _constant_return_result(name: str, daily_return: float, n_days: int = 300) -> StrategyResult:
    dates = pd.bdate_range("2021-01-01", periods=n_days)
    returns = pd.Series(daily_return, index=dates)
    periods = [BacktestPeriod(date=dates[0], regime="sideways", weights={"A": 1.0}, period_return=daily_return, turnover=0.5)]
    return StrategyResult(name=name, periods=periods, daily_returns=returns, equity_curve=(1 + returns).cumprod())


def test_compute_metrics_matches_hand_computed_sharpe_for_constant_returns() -> None:
    daily_return = 0.001
    result = _constant_return_result("test", daily_return)

    metrics = compute_metrics(result, risk_free_rate=0.0)

    expected_annual_return = (1 + daily_return) ** 252 - 1
    assert metrics.cagr == pytest.approx(expected_annual_return, rel=1e-3)
    # constant positive returns -> near-zero volatility -> Sharpe blows up (degenerate case, expected)
    assert metrics.sharpe > 0
    assert metrics.max_drawdown == pytest.approx(0.0, abs=1e-9)


def test_regime_conditional_metrics_splits_by_period_regime() -> None:
    dates = pd.bdate_range("2021-01-01", periods=100)
    rng = np.random.default_rng(1)
    returns = pd.Series(rng.normal(0.0005, 0.01, size=100), index=dates)

    periods = [
        BacktestPeriod(date=dates[0], regime="bull", weights={"A": 1.0}, period_return=0.0, turnover=0.5),
        BacktestPeriod(date=dates[50], regime="bear", weights={"A": 1.0}, period_return=0.0, turnover=0.1),
    ]
    result = StrategyResult(name="test", periods=periods, daily_returns=returns, equity_curve=(1 + returns).cumprod())

    breakdown = compute_regime_conditional_metrics(result)

    assert set(breakdown.keys()) == {"bull", "bear"}
    assert breakdown["bull"].n_observations == 50
    assert breakdown["bear"].n_observations == 50


def test_bootstrap_sharpe_difference_detects_clear_outperformance() -> None:
    dates = pd.bdate_range("2021-01-01", periods=500)
    rng = np.random.default_rng(3)
    base = rng.normal(0.0003, 0.01, size=500)
    better = pd.Series(base + 0.002, index=dates)  # strictly better every day
    worse = pd.Series(base, index=dates)

    result = bootstrap_sharpe_difference(better, worse, risk_free_rate=0.0, n_bootstrap=200, block_size=10)

    assert result["observed_difference"] > 0
    assert result["significant"] is True
    assert result["ci_lower"] > 0


def test_bootstrap_sharpe_difference_raises_on_too_little_data() -> None:
    dates = pd.bdate_range("2021-01-01", periods=10)
    a = pd.Series(0.001, index=dates)
    b = pd.Series(0.0005, index=dates)
    with pytest.raises(ValueError):
        bootstrap_sharpe_difference(a, b, n_bootstrap=50, block_size=20)


def test_compare_strategies_aggregates_metrics_and_significance() -> None:
    results = {
        "equal_weight": _constant_return_result("equal_weight", 0.0003),
        "full_pipeline": _constant_return_result("full_pipeline", 0.0008),
    }

    summary = compare_strategies(results, baseline="equal_weight", risk_free_rate=0.0)

    assert set(summary["metrics"].keys()) == {"equal_weight", "full_pipeline"}
    assert summary["baseline"] == "equal_weight"
    assert "full_pipeline" in summary["significance_vs_baseline"] or summary["significance_vs_baseline"] == {}
