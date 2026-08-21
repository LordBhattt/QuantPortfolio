"""Walk-forward backtesting engine.

Replays the existing optimization building blocks (Ledoit-Wolf covariance,
Black-Litterman blending, HMM regime scaling, constrained MVO) against
historical returns to measure out-of-sample performance, instead of only
asserting it from a single anecdotal portfolio. At each monthly rebalance
date, a strategy only ever sees returns strictly *before* that date -- the
day of and after the rebalance are held out, so there is no lookahead bias.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterator

import numpy as np
import pandas as pd

from backend.quant.black_litterman import BLInputs, black_litterman_returns
from backend.quant.covariance import compute_covariance, scale_covariance_by_regime
from backend.quant.mvo import constrained_mvo
from backend.quant.regime import RegimeDetector

DEFAULT_LOOKBACK_DAYS = 756  # ~3 trading years
DEFAULT_TRANSACTION_COST_BPS = 10.0
TRADING_DAYS_PER_YEAR = 252

StrategyFn = Callable[[pd.DataFrame, list[str], list[str], "int | None"], dict[str, float]]


@dataclass
class BacktestPeriod:
    date: pd.Timestamp
    regime: str
    weights: dict[str, float]
    period_return: float
    turnover: float


@dataclass
class StrategyResult:
    name: str
    periods: list[BacktestPeriod] = field(default_factory=list)
    daily_returns: pd.Series = field(default_factory=pd.Series)
    equity_curve: pd.Series = field(default_factory=pd.Series)


def _equal_weight(window: pd.DataFrame, tickers: list[str], asset_classes: list[str], regime_state: int | None) -> dict[str, float]:
    del window, asset_classes, regime_state
    return {ticker: 1.0 / len(tickers) for ticker in tickers}


def _static_mvo(window: pd.DataFrame, tickers: list[str], asset_classes: list[str], regime_state: int | None) -> dict[str, float]:
    del regime_state
    mu = window.mean().values * TRADING_DAYS_PER_YEAR
    cov = window.cov().values * TRADING_DAYS_PER_YEAR
    return constrained_mvo(mu, cov, tickers, asset_classes, None, risk_tolerance=0.5)


def _mvo_ledoit_wolf(window: pd.DataFrame, tickers: list[str], asset_classes: list[str], regime_state: int | None) -> dict[str, float]:
    del regime_state
    mu = window.mean().values * TRADING_DAYS_PER_YEAR
    cov = compute_covariance(window, method="ledoit_wolf", annualise=True)
    return constrained_mvo(mu, cov, tickers, asset_classes, None, risk_tolerance=0.5)


def _full_pipeline(window: pd.DataFrame, tickers: list[str], asset_classes: list[str], regime_state: int | None) -> dict[str, float]:
    cov = compute_covariance(window, method="ledoit_wolf", annualise=True)
    if regime_state is not None:
        cov = scale_covariance_by_regime(cov, regime_state)
    market_weights = np.ones(len(tickers)) / len(tickers)
    bl_inputs = BLInputs(cov=cov, market_weights=market_weights, risk_aversion=2.5, tau=0.025, P=None, Q=None, Omega=None)
    mu = black_litterman_returns(bl_inputs)
    return constrained_mvo(mu, cov, tickers, asset_classes, None, risk_tolerance=0.5)


STRATEGIES: dict[str, StrategyFn] = {
    "equal_weight": _equal_weight,
    "static_mvo": _static_mvo,
    "mvo_ledoit_wolf": _mvo_ledoit_wolf,
    "full_pipeline": _full_pipeline,
}


def _monthly_rebalance_dates(dates: pd.DatetimeIndex) -> list[pd.Timestamp]:
    periods = dates.to_period("M")
    seen: set = set()
    result: list[pd.Timestamp] = []
    for date, period in zip(dates, periods):
        if period not in seen:
            seen.add(period)
            result.append(date)
    return result


def _lookback_window(returns_df: pd.DataFrame, reb_date: pd.Timestamp, lookback_days: int) -> pd.DataFrame:
    """Returns strictly before `reb_date`, most recent `lookback_days` of them."""
    prior = returns_df.loc[:reb_date].iloc[:-1]
    return prior.tail(lookback_days)


@dataclass
class RebalancePoint:
    index: int
    date: pd.Timestamp
    window: pd.DataFrame
    holding_period: pd.DataFrame
    regime_state: int | None
    regime_label: str
    is_last: bool


def iterate_rebalances(
    returns_df: pd.DataFrame,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    regime_detector: RegimeDetector | None = None,
) -> Iterator[RebalancePoint]:
    """Shared no-lookahead walk-forward mechanics, reused by every strategy
    (including the adaptive bandit in strategy_bandit.py) so all of them
    see exactly the same rebalance dates, windows, and holding periods."""
    dates = returns_df.index
    rebalance_dates = [
        date for date in _monthly_rebalance_dates(dates) if dates.get_loc(date) >= lookback_days
    ]
    if len(rebalance_dates) < 2:
        raise ValueError("insufficient history for a walk-forward backtest: need more cached data or a shorter lookback")

    for index, reb_date in enumerate(rebalance_dates):
        window = _lookback_window(returns_df, reb_date, lookback_days)
        if len(window) < lookback_days * 0.5:
            continue

        regime_state: int | None = None
        regime_label = "sideways"
        if regime_detector is not None and regime_detector.is_fitted:
            try:
                market_proxy = window.iloc[:, 0]
                regime_state, _ = regime_detector.predict(market_proxy)
                regime_label = regime_detector.regime_label(regime_state)
            except Exception:
                regime_state = None

        is_last = index + 1 >= len(rebalance_dates)
        next_date = rebalance_dates[index + 1] if not is_last else dates[-1]
        holding_period = returns_df.loc[reb_date:next_date]
        if not is_last:
            holding_period = holding_period.iloc[:-1]
        if holding_period.empty:
            continue

        yield RebalancePoint(
            index=index,
            date=reb_date,
            window=window,
            holding_period=holding_period,
            regime_state=regime_state,
            regime_label=regime_label,
            is_last=is_last,
        )


def run_walk_forward_backtest(
    returns_df: pd.DataFrame,
    asset_classes: dict[str, str],
    strategies: dict[str, StrategyFn] | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    transaction_cost_bps: float = DEFAULT_TRANSACTION_COST_BPS,
    regime_detector: RegimeDetector | None = None,
) -> dict[str, StrategyResult]:
    if returns_df.empty:
        raise ValueError("returns_df is empty")
    if strategies is None:
        strategies = STRATEGIES

    tickers = list(returns_df.columns)
    asset_class_list = [asset_classes.get(ticker, "stock") for ticker in tickers]

    results: dict[str, StrategyResult] = {}
    for name, strategy_fn in strategies.items():
        periods: list[BacktestPeriod] = []
        daily_return_chunks: list[pd.Series] = []
        prev_weights: dict[str, float] = {ticker: 0.0 for ticker in tickers}

        for point in iterate_rebalances(returns_df, lookback_days, regime_detector):
            try:
                weights = strategy_fn(point.window, tickers, asset_class_list, point.regime_state)
            except Exception:
                weights = {ticker: 1.0 / len(tickers) for ticker in tickers}

            turnover = sum(abs(weights[ticker] - prev_weights.get(ticker, 0.0)) for ticker in tickers) / 2.0
            cost = turnover * transaction_cost_bps / 10000.0

            weight_vector = np.array([weights[ticker] for ticker in tickers])
            period_returns = pd.Series(point.holding_period.values @ weight_vector, index=point.holding_period.index)
            period_returns.iloc[0] -= cost

            period_return = float((1.0 + period_returns).prod() - 1.0)
            periods.append(
                BacktestPeriod(
                    date=point.date,
                    regime=point.regime_label,
                    weights=weights,
                    period_return=period_return,
                    turnover=turnover,
                )
            )
            daily_return_chunks.append(period_returns)
            prev_weights = weights

        if not daily_return_chunks:
            continue

        full_daily_returns = pd.concat(daily_return_chunks).sort_index()
        full_daily_returns = full_daily_returns[~full_daily_returns.index.duplicated(keep="first")]
        equity_curve = (1.0 + full_daily_returns).cumprod()
        results[name] = StrategyResult(
            name=name,
            periods=periods,
            daily_returns=full_daily_returns,
            equity_curve=equity_curve,
        )

    return results
