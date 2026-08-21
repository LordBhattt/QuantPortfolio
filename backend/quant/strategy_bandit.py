"""Adaptive regime-conditioned strategy selector: a Thompson Sampling
contextual bandit.

Context = the detected HMM market regime (bull/sideways/bear/unknown).
Arms = a small set of existing optimization strategies (static MVO,
MVO+Ledoit-Wolf, the full BL+LW+HMM pipeline). Reward = the realized,
volatility-normalized return of the following holding period.

This is deliberately *not* a deep-RL policy: it keeps a small, inspectable
table of per-(regime, arm) posteriors, matching the report's own literature
survey preference for interpretable models over black-box RL policies. It
answers a different question than the rest of the backtest engine: instead
of asking "does the fixed production pipeline beat naive baselines?", it
asks "can we do even better by adaptively switching strategies based on
which one has actually worked best in the current regime so far?" -- and
its own answer is graded by the exact same out-of-sample walk-forward
machinery, with no lookahead (the bandit only ever updates on rewards from
periods that have already completed).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from backend.quant.backtest import (
    DEFAULT_LOOKBACK_DAYS,
    DEFAULT_TRANSACTION_COST_BPS,
    STRATEGIES,
    BacktestPeriod,
    StrategyResult,
    iterate_rebalances,
)
from backend.quant.regime import RegimeDetector

DEFAULT_ARMS = ("static_mvo", "mvo_ledoit_wolf", "full_pipeline")
REGIME_CONTEXTS = ("bull", "sideways", "bear", "unknown")
ADAPTIVE_STRATEGY_NAME = "adaptive_bandit"


@dataclass
class _ArmPosterior:
    """Running (online) mean/variance of realized reward for one (regime, arm) pair."""

    n: int = 0
    mean: float = 0.0
    _m2: float = 0.0

    def update(self, reward: float) -> None:
        self.n += 1
        delta = reward - self.mean
        self.mean += delta / self.n
        delta2 = reward - self.mean
        self._m2 += delta * delta2

    @property
    def variance(self) -> float:
        if self.n < 2:
            return 1.0  # wide prior until there is evidence
        return self._m2 / (self.n - 1)


class RegimeStrategyBandit:
    """Thompson-Sampling contextual bandit over (regime, strategy) pairs."""

    def __init__(self, arms: tuple[str, ...] = DEFAULT_ARMS, seed: int = 7) -> None:
        self.arms = arms
        self._rng = np.random.default_rng(seed)
        self._posteriors: dict[tuple[str, str], _ArmPosterior] = {
            (regime, arm): _ArmPosterior() for regime in REGIME_CONTEXTS for arm in arms
        }

    def _normalize_regime(self, regime: str) -> str:
        return regime if regime in REGIME_CONTEXTS else "unknown"

    def select_arm(self, regime: str) -> str:
        regime = self._normalize_regime(regime)
        samples: dict[str, float] = {}
        for arm in self.arms:
            posterior = self._posteriors[(regime, arm)]
            std = float(np.sqrt(posterior.variance / max(posterior.n, 1)))
            samples[arm] = float(self._rng.normal(posterior.mean, std if std > 0 else 1e-6))
        return max(samples, key=samples.get)

    def update(self, regime: str, arm: str, reward: float) -> None:
        regime = self._normalize_regime(regime)
        self._posteriors[(regime, arm)].update(reward)

    def posterior_summary(self) -> dict[str, dict[str, dict[str, float]]]:
        summary: dict[str, dict[str, dict[str, float]]] = {}
        for (regime, arm), posterior in self._posteriors.items():
            summary.setdefault(regime, {})[arm] = {
                "mean": posterior.mean,
                "variance": posterior.variance,
                "n": posterior.n,
            }
        return summary


def _risk_adjusted_reward(period_returns: pd.Series) -> float:
    """Volatility-normalized reward for one holding period (a short-horizon Sharpe-like score)."""
    std = float(period_returns.std())
    mean = float(period_returns.mean())
    if std <= 1e-12:
        return mean  # degenerate (near-zero-vol) period: fall back to raw mean
    return mean / std


def run_adaptive_bandit_backtest(
    returns_df: pd.DataFrame,
    asset_classes: dict[str, str],
    arm_strategies: dict[str, "callable"] | None = None,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    transaction_cost_bps: float = DEFAULT_TRANSACTION_COST_BPS,
    regime_detector: RegimeDetector | None = None,
    bandit: RegimeStrategyBandit | None = None,
) -> tuple[StrategyResult, RegimeStrategyBandit]:
    """Walk-forward backtest of the adaptive bandit strategy.

    At each rebalance date the bandit picks one of `arm_strategies` given the
    detected regime, that strategy's weights are used for the holding
    period exactly like any other strategy in run_walk_forward_backtest,
    and only *after* the holding period's return is realized does the
    bandit update its posterior for (regime, chosen arm) -- so there is no
    lookahead, identical to the rest of the backtest engine.
    """
    if returns_df.empty:
        raise ValueError("returns_df is empty")
    if arm_strategies is None:
        arm_strategies = {name: STRATEGIES[name] for name in DEFAULT_ARMS}
    if bandit is None:
        bandit = RegimeStrategyBandit(arms=tuple(arm_strategies.keys()))

    tickers = list(returns_df.columns)
    asset_class_list = [asset_classes.get(ticker, "stock") for ticker in tickers]

    periods: list[BacktestPeriod] = []
    daily_return_chunks: list[pd.Series] = []
    prev_weights: dict[str, float] = {ticker: 0.0 for ticker in tickers}

    for point in iterate_rebalances(returns_df, lookback_days, regime_detector):
        chosen_arm = bandit.select_arm(point.regime_label)
        strategy_fn = arm_strategies[chosen_arm]

        try:
            weights = strategy_fn(point.window, tickers, asset_class_list, point.regime_state)
        except Exception:
            weights = {ticker: 1.0 / len(tickers) for ticker in tickers}

        turnover = sum(abs(weights[ticker] - prev_weights.get(ticker, 0.0)) for ticker in tickers) / 2.0
        cost = turnover * transaction_cost_bps / 10000.0

        weight_vector = np.array([weights[ticker] for ticker in tickers])
        period_returns = pd.Series(point.holding_period.values @ weight_vector, index=point.holding_period.index)
        period_returns.iloc[0] -= cost

        reward = _risk_adjusted_reward(period_returns)
        bandit.update(point.regime_label, chosen_arm, reward)

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
        raise ValueError("adaptive bandit backtest produced no periods")

    full_daily_returns = pd.concat(daily_return_chunks).sort_index()
    full_daily_returns = full_daily_returns[~full_daily_returns.index.duplicated(keep="first")]
    equity_curve = (1.0 + full_daily_returns).cumprod()
    result = StrategyResult(
        name=ADAPTIVE_STRATEGY_NAME,
        periods=periods,
        daily_returns=full_daily_returns,
        equity_curve=equity_curve,
    )
    return result, bandit
