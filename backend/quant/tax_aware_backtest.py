"""Tax-aware backtest: replays an existing strategy's walk-forward target
weights through a real lot-level portfolio ledger under three execution
policies -- a frictionless no-tax baseline, naive FIFO lot selection, and
tax-aware lot selection -- producing equity curves so the tax drag can be
*measured* as the one isolated difference, not asserted.

Deliberately reuses the exact target weights the walk-forward engine
already computed for a strategy (by default `full_pipeline`, the
production default) -- this module does not re-run optimization, it only
changes *how* the resulting rebalance is executed at the trade level.
Everything upstream (which assets, what weights, when to rebalance) stays
identical between the two policies; only lot selection differs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from backend.quant.backtest import StrategyResult
from backend.quant.tax_lot_ledger import PortfolioLedger, rebalance_to_target
from backend.quant.tax_rules import TaxYearTracker

DEFAULT_STARTING_CAPITAL = 1_000_000.0
# "no_tax" is a frictionless baseline: identical trade sizing and lot
# mechanics as "fifo", but with tax switched off. It exists so "tax drag"
# can be isolated as the ONLY difference between it and the taxed
# policies -- comparing against the walk-forward engine's own equity
# curve instead would also pick up its (different) transaction-cost
# convention and understate/overstate the tax effect.
POLICIES = ("no_tax", "fifo", "tax_aware")
_LOT_POLICY_FOR = {"no_tax": "fifo", "fifo": "fifo", "tax_aware": "tax_aware"}


@dataclass
class TaxAwareResult:
    policy: str
    equity_curve: pd.Series
    daily_returns: pd.Series
    total_tax_paid: float
    tax_by_asset_class: dict[str, float] = field(default_factory=dict)


def _build_close_price_matrix(price_data: dict[str, pd.DataFrame]) -> pd.DataFrame:
    closes = {ticker: frame["close"].astype(float) for ticker, frame in price_data.items()}
    return pd.DataFrame(closes).sort_index().ffill()


def run_tax_aware_backtest(
    strategy_result: StrategyResult,
    price_data: dict[str, pd.DataFrame],
    asset_classes: dict[str, str],
    starting_capital: float = DEFAULT_STARTING_CAPITAL,
) -> dict[str, TaxAwareResult]:
    if not strategy_result.periods:
        raise ValueError("strategy_result has no periods to replay")

    price_matrix = _build_close_price_matrix(price_data)
    periods = strategy_result.periods
    last_date = strategy_result.daily_returns.index.max()

    results: dict[str, TaxAwareResult] = {}
    for policy in POLICIES:
        ledger = PortfolioLedger(cash=starting_capital)
        tracker = TaxYearTracker()
        apply_tax = policy != "no_tax"
        lot_policy = _LOT_POLICY_FOR[policy]
        tax_by_asset_class: dict[str, float] = {}
        equity_index: list[pd.Timestamp] = []
        equity_values: list[float] = []

        for index, period in enumerate(periods):
            reb_date = period.date
            if reb_date not in price_matrix.index:
                continue
            prices = price_matrix.loc[reb_date].dropna().to_dict()

            disposals = rebalance_to_target(
                ledger, period.weights, asset_classes, prices, reb_date.date(), tracker, lot_policy, apply_tax
            )
            for disposal in disposals:
                asset_class = asset_classes.get(disposal.ticker, "stock")
                tax_by_asset_class[asset_class] = tax_by_asset_class.get(asset_class, 0.0) + disposal.tax_owed

            is_last = index + 1 >= len(periods)
            next_date = periods[index + 1].date if not is_last else last_date
            holding_dates = price_matrix.loc[reb_date:next_date].index
            if not is_last:
                holding_dates = holding_dates[:-1]

            for day in holding_dates:
                day_prices = price_matrix.loc[day].dropna().to_dict()
                equity_index.append(day)
                equity_values.append(ledger.holdings_value(day_prices))

        if not equity_values:
            raise ValueError(f"tax-aware backtest for policy={policy} produced no equity points")

        equity_series = pd.Series(equity_values, index=pd.DatetimeIndex(equity_index)).sort_index()
        equity_series = equity_series[~equity_series.index.duplicated(keep="last")]
        normalized = equity_series / starting_capital
        daily_returns = normalized.pct_change().dropna()

        results[policy] = TaxAwareResult(
            policy=policy,
            equity_curve=normalized,
            daily_returns=daily_returns,
            total_tax_paid=sum(tax_by_asset_class.values()),
            tax_by_asset_class=tax_by_asset_class,
        )

    return results


def to_strategy_result(tax_result: TaxAwareResult, name: str) -> StrategyResult:
    """Wraps a TaxAwareResult as a StrategyResult so the existing
    backtest_stats helpers (CAGR/Sharpe/Sortino/MaxDD/...) can be reused
    without duplicating their computation."""
    return StrategyResult(
        name=name,
        periods=[],
        daily_returns=tax_result.daily_returns,
        equity_curve=tax_result.equity_curve,
    )
