"""Performance statistics, regime-conditional breakdown, and bootstrap
significance testing for backtest results.

Reuses the existing Sharpe/Sortino/Calmar/VaR/CVaR/drawdown helpers from
backend/quant/risk_engine.py instead of redefining them, so backtest metrics
and live risk-page metrics are always computed the same way.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from backend.quant.backtest import StrategyResult
from backend.quant.risk_engine import (
    calmar_ratio,
    historical_cvar,
    historical_var,
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
)

TRADING_DAYS_PER_YEAR = 252
REGIME_LABELS = ("bull", "sideways", "bear")
MIN_REGIME_OBSERVATIONS = 20


@dataclass
class StrategyMetrics:
    name: str
    cagr: float
    annual_volatility: float
    sharpe: float
    sortino: float
    calmar: float
    max_drawdown: float
    var_95: float
    cvar_95: float
    avg_turnover: float
    n_periods: int
    n_observations: int


def compute_metrics(result: StrategyResult, risk_free_rate: float | None = None) -> StrategyMetrics:
    returns = result.daily_returns
    if returns.empty:
        raise ValueError(f"strategy {result.name} has no daily returns")

    n_years = len(returns) / TRADING_DAYS_PER_YEAR
    cumulative = float((1.0 + returns).prod())
    cagr = cumulative ** (1.0 / n_years) - 1.0 if n_years > 0 and cumulative > 0 else 0.0
    avg_turnover = float(np.mean([period.turnover for period in result.periods])) if result.periods else 0.0

    return StrategyMetrics(
        name=result.name,
        cagr=cagr,
        annual_volatility=float(returns.std() * np.sqrt(TRADING_DAYS_PER_YEAR)),
        sharpe=sharpe_ratio(returns, risk_free_rate),
        sortino=sortino_ratio(returns, risk_free_rate),
        calmar=calmar_ratio(returns),
        max_drawdown=max_drawdown(returns),
        var_95=historical_var(returns, 0.95),
        cvar_95=historical_cvar(returns, 0.95),
        avg_turnover=avg_turnover,
        n_periods=len(result.periods),
        n_observations=len(returns),
    )


def _regime_label_by_date(result: StrategyResult) -> dict[pd.Timestamp, str]:
    labels: dict[pd.Timestamp, str] = {}
    if not result.periods:
        return labels

    boundaries = [period.date for period in result.periods[1:]] + [None]
    for period, next_date in zip(result.periods, boundaries):
        if next_date is None:
            mask = result.daily_returns.index >= period.date
        else:
            mask = (result.daily_returns.index >= period.date) & (result.daily_returns.index < next_date)
        for date in result.daily_returns.index[mask]:
            labels[date] = period.regime
    return labels


def compute_regime_conditional_metrics(
    result: StrategyResult, risk_free_rate: float | None = None
) -> dict[str, StrategyMetrics]:
    """Metrics computed only over daily returns whose holding period was tagged with each regime."""
    labels = _regime_label_by_date(result)
    breakdown: dict[str, StrategyMetrics] = {}
    for regime in REGIME_LABELS:
        dates = sorted(date for date, label in labels.items() if label == regime)
        if len(dates) < MIN_REGIME_OBSERVATIONS:
            continue
        subset = result.daily_returns.loc[dates]
        subset_result = StrategyResult(
            name=f"{result.name}:{regime}",
            periods=[],
            daily_returns=subset,
            equity_curve=(1.0 + subset).cumprod(),
        )
        breakdown[regime] = compute_metrics(subset_result, risk_free_rate)
    return breakdown


def bootstrap_sharpe_difference(
    returns_a: pd.Series,
    returns_b: pd.Series,
    risk_free_rate: float | None = None,
    n_bootstrap: int = 2000,
    block_size: int = 20,
    confidence: float = 0.95,
    seed: int = 42,
) -> dict[str, float | bool]:
    """Block-bootstrap confidence interval for Sharpe(a) - Sharpe(b).

    Resampling in contiguous blocks (rather than i.i.d. days) preserves the
    short-run autocorrelation in daily returns; an i.i.d. bootstrap would
    understate the true uncertainty in the Sharpe estimate.
    """
    aligned = pd.concat([returns_a.rename("a"), returns_b.rename("b")], axis=1).dropna()
    n = len(aligned)
    if n < block_size * 5:
        raise ValueError("not enough overlapping observations for a block bootstrap")

    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(n / block_size))
    values = aligned.values

    observed = sharpe_ratio(aligned["a"], risk_free_rate) - sharpe_ratio(aligned["b"], risk_free_rate)

    diffs = np.empty(n_bootstrap)
    for i in range(n_bootstrap):
        starts = rng.integers(0, n - block_size + 1, size=n_blocks)
        sample_idx = np.concatenate([np.arange(start, start + block_size) for start in starts])[:n]
        sample = values[sample_idx]
        diffs[i] = sharpe_ratio(pd.Series(sample[:, 0]), risk_free_rate) - sharpe_ratio(pd.Series(sample[:, 1]), risk_free_rate)

    lower_pct = (1.0 - confidence) / 2.0 * 100
    upper_pct = (1.0 + confidence) / 2.0 * 100
    ci_lower = float(np.percentile(diffs, lower_pct))
    ci_upper = float(np.percentile(diffs, upper_pct))

    return {
        "observed_difference": float(observed),
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "confidence": confidence,
        "significant": bool(ci_lower > 0 or ci_upper < 0),
    }


def compare_strategies(
    results: dict[str, StrategyResult],
    baseline: str = "equal_weight",
    risk_free_rate: float | None = None,
) -> dict[str, object]:
    """Convenience aggregate: per-strategy metrics, regime breakdown, and
    bootstrap significance of each strategy's Sharpe vs. the baseline."""
    metrics = {name: compute_metrics(result, risk_free_rate) for name, result in results.items()}
    regime_metrics = {name: compute_regime_conditional_metrics(result, risk_free_rate) for name, result in results.items()}

    significance: dict[str, dict[str, float | bool]] = {}
    if baseline in results:
        for name, result in results.items():
            if name == baseline:
                continue
            try:
                significance[name] = bootstrap_sharpe_difference(
                    result.daily_returns, results[baseline].daily_returns, risk_free_rate
                )
            except ValueError:
                continue

    return {
        "metrics": metrics,
        "regime_metrics": regime_metrics,
        "significance_vs_baseline": significance,
        "baseline": baseline,
    }
