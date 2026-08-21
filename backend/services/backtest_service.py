"""Backtest orchestration: loads the locally cached historical universe,
replays the walk-forward engine and the adaptive bandit, and formats the
result for the API. Uses only the local parquet cache from
backend/quant/backtest_data.py -- no live market data calls happen on this
path, which is what keeps repeated backtest requests cheap and safe for
the free-tier data providers.
"""

from __future__ import annotations

import asyncio

from backend.errors import AppError
from backend.quant.backtest import DEFAULT_LOOKBACK_DAYS, DEFAULT_TRANSACTION_COST_BPS, run_walk_forward_backtest
from backend.quant.backtest_data import load_cached_prices
from backend.quant.backtest_stats import StrategyMetrics, _regime_label_by_date, compare_strategies, compute_metrics
from backend.quant.backtest_universe import BACKTEST_UNIVERSE
from backend.quant.regime import RegimeDetector
from backend.quant.returns import align_returns
from backend.quant.strategy_bandit import run_adaptive_bandit_backtest
from backend.quant.tax_aware_backtest import DEFAULT_STARTING_CAPITAL, run_tax_aware_backtest, to_strategy_result
from backend.schemas.backtest import (
    BacktestResponse,
    BanditPosteriorEntry,
    EquityCurvePoint,
    RegimeBreakdownResponse,
    SignificanceResponse,
    StrategyMetricsResponse,
    StrategySeriesResponse,
    TaxAwareComparisonResponse,
    TaxPolicyResult,
)
from backend.services.optimization_service import get_regime_detector

MIN_CACHED_ASSETS = 4
DEFAULT_FX_USD_INR = 83.5
TAX_AWARE_STRATEGY = "full_pipeline"

_result_cache: dict[tuple[int, float, str], BacktestResponse] = {}


def _to_metrics_response(metrics: StrategyMetrics) -> StrategyMetricsResponse:
    return StrategyMetricsResponse(
        cagr=metrics.cagr,
        annual_volatility=metrics.annual_volatility,
        sharpe=metrics.sharpe,
        sortino=metrics.sortino,
        calmar=metrics.calmar,
        max_drawdown=metrics.max_drawdown,
        var_95=metrics.var_95,
        cvar_95=metrics.cvar_95,
        avg_turnover=metrics.avg_turnover,
        n_periods=metrics.n_periods,
        n_observations=metrics.n_observations,
    )


def _build_tax_comparison(
    strategy_result, price_data: dict, asset_classes: dict[str, str]
) -> TaxAwareComparisonResponse | None:
    """Replays `strategy_result`'s already-computed weights through the
    lot ledger under no_tax/fifo/tax_aware policies. Returns None rather
    than raising if there isn't enough lot history to simulate (e.g. a
    strategy with fewer than 2 rebalance periods), since this is a
    supplementary comparison, not core to the main backtest response."""
    try:
        tax_results = run_tax_aware_backtest(
            strategy_result, price_data, asset_classes, starting_capital=DEFAULT_STARTING_CAPITAL
        )
    except ValueError:
        return None

    policies_payload: list[TaxPolicyResult] = []
    finals: dict[str, float] = {}
    for policy_name, result in tax_results.items():
        metrics = compute_metrics(to_strategy_result(result, policy_name))
        equity_points = [
            EquityCurvePoint(date=str(date.date()), value=float(value)) for date, value in result.equity_curve.items()
        ]
        policies_payload.append(
            TaxPolicyResult(
                policy=policy_name,
                equity_curve=equity_points,
                metrics=_to_metrics_response(metrics),
                total_tax_paid=result.total_tax_paid,
                tax_by_asset_class=result.tax_by_asset_class,
            )
        )
        finals[policy_name] = float(result.equity_curve.iloc[-1])

    no_tax_final = finals.get("no_tax", 0.0)
    fifo_final = finals.get("fifo", 0.0)
    aware_final = finals.get("tax_aware", 0.0)

    naive_drag_pct = (1.0 - fifo_final / no_tax_final) * 100.0 if no_tax_final > 0 else 0.0
    savings_pct = (aware_final / fifo_final - 1.0) * 100.0 if fifo_final > 0 else 0.0
    drag_amount = no_tax_final - fifo_final
    recovery_pct = ((aware_final - fifo_final) / drag_amount) * 100.0 if drag_amount > 1e-9 else 0.0

    return TaxAwareComparisonResponse(
        strategy=strategy_result.name,
        starting_capital=DEFAULT_STARTING_CAPITAL,
        policies=policies_payload,
        naive_tax_drag_pct=naive_drag_pct,
        tax_aware_savings_pct=savings_pct,
        tax_aware_recovery_pct=recovery_pct,
    )


async def run_backtest(
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    transaction_cost_bps: float = DEFAULT_TRANSACTION_COST_BPS,
    baseline: str = "equal_weight",
    regime_detector: RegimeDetector | None = None,
) -> BacktestResponse:
    cache_key = (lookback_days, transaction_cost_bps, baseline)
    if cache_key in _result_cache:
        return _result_cache[cache_key]

    if regime_detector is None:
        regime_detector = get_regime_detector()

    price_data = {}
    for asset in BACKTEST_UNIVERSE:
        frame = load_cached_prices(asset.ticker)
        if frame is not None:
            price_data[asset.ticker] = frame

    if len(price_data) < MIN_CACHED_ASSETS:
        raise AppError(
            "Backtest unavailable",
            "backtest_dataset_missing",
            "Historical dataset cache is empty or too small. Run "
            "`python -m backend.scripts.build_backtest_dataset` to build it.",
            503,
        )

    currencies = {asset.ticker: asset.currency for asset in BACKTEST_UNIVERSE if asset.ticker in price_data}
    classes = {asset.ticker: asset.asset_class for asset in BACKTEST_UNIVERSE if asset.ticker in price_data}

    loop = asyncio.get_running_loop()
    returns_df = await loop.run_in_executor(None, align_returns, price_data, currencies, "USD", DEFAULT_FX_USD_INR)
    if returns_df.empty:
        raise AppError(
            "Backtest unavailable",
            "insufficient_returns",
            "Unable to build an aligned return matrix from the cached historical data",
            503,
        )

    try:
        results = await loop.run_in_executor(
            None,
            run_walk_forward_backtest,
            returns_df,
            classes,
            None,
            lookback_days,
            transaction_cost_bps,
            regime_detector,
        )
        adaptive_result, bandit = await loop.run_in_executor(
            None,
            run_adaptive_bandit_backtest,
            returns_df,
            classes,
            None,
            lookback_days,
            transaction_cost_bps,
            regime_detector,
        )
    except ValueError as exc:
        raise AppError("Backtest failed", "backtest_insufficient_history", str(exc), 400) from exc

    results = dict(results)
    results[adaptive_result.name] = adaptive_result

    summary = compare_strategies(results, baseline=baseline, risk_free_rate=None)

    strategies_payload: list[StrategySeriesResponse] = []
    for name, result in results.items():
        metrics = summary["metrics"][name]
        regime_breakdown = summary["regime_metrics"].get(name, {})
        regime_by_date = _regime_label_by_date(result)
        equity_points = [
            EquityCurvePoint(date=str(date.date()), value=float(value), regime=regime_by_date.get(date))
            for date, value in result.equity_curve.items()
        ]
        strategies_payload.append(
            StrategySeriesResponse(
                name=name,
                equity_curve=equity_points,
                metrics=_to_metrics_response(metrics),
                regime_breakdown=[
                    RegimeBreakdownResponse(regime=regime, metrics=_to_metrics_response(regime_metrics))
                    for regime, regime_metrics in regime_breakdown.items()
                ],
            )
        )

    significance_payload = [
        SignificanceResponse(strategy=name, **significance)
        for name, significance in summary["significance_vs_baseline"].items()
    ]

    bandit_payload = [
        BanditPosteriorEntry(regime=regime, arm=arm, **entry)
        for regime, arms in bandit.posterior_summary().items()
        for arm, entry in arms.items()
    ]

    tax_comparison = None
    tax_strategy_result = results.get(TAX_AWARE_STRATEGY)
    if tax_strategy_result is not None:
        tax_comparison = await loop.run_in_executor(
            None, _build_tax_comparison, tax_strategy_result, price_data, classes
        )

    response = BacktestResponse(
        universe=list(price_data.keys()),
        lookback_days=lookback_days,
        transaction_cost_bps=transaction_cost_bps,
        baseline=baseline,
        data_through=str(returns_df.index.max().date()),
        strategies=strategies_payload,
        significance_vs_baseline=significance_payload,
        bandit_posterior=bandit_payload,
        tax_comparison=tax_comparison,
    )
    _result_cache[cache_key] = response
    return response
