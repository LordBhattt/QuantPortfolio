"""Walk-forward backtest engine with no lookahead bias."""

import logging
from typing import Any

import numpy as np
import pandas as pd

from backend.config import get_settings
from backend.services.optimization_service import optimize_from_returns

settings = get_settings()
logger = logging.getLogger(__name__)

REBALANCE_FREQ = {
    "weekly": 5,
    "monthly": 21,
    "quarterly": 63,
}


def _compute_metrics(
    equity: pd.Series,
    turnovers: list[float],
    initial_value: float,
    rf: float,
) -> dict:
    """Compute performance metrics for a strategy equity curve."""
    years = max(len(equity) / 252.0, 1.0 / 252.0)
    final_value = float(equity.iloc[-1])
    total_profit = final_value - initial_value

    daily_returns = equity.pct_change().dropna()

    if len(daily_returns) > 0 and final_value > 0 and initial_value > 0:
        cagr = float((final_value / initial_value) ** (1.0 / years) - 1.0)
    else:
        cagr = 0.0

    vol = float(daily_returns.std() * np.sqrt(252)) if len(daily_returns) > 1 else 0.0
    sharpe = float((cagr - rf) / vol) if vol > 1e-6 else 0.0

    neg_returns = daily_returns[daily_returns < 0]
    downside_std = float(neg_returns.std() * np.sqrt(252)) if len(neg_returns) > 1 else 0.0
    sortino = float((cagr - rf) / downside_std) if downside_std > 1e-6 else 0.0

    running_max = equity.cummax()
    drawdown_series = (equity - running_max) / running_max.replace(0, np.nan)
    drawdown_series = drawdown_series.fillna(0.0)
    max_dd = float(drawdown_series.min())  # negative or 0.0

    calmar = float(cagr / abs(max_dd)) if abs(max_dd) > 1e-6 else 0.0
    avg_turnover = float(np.mean(turnovers)) if turnovers else 0.0

    return {
        "final_value": round(final_value, 2),
        "total_profit_inr": round(total_profit, 2),
        "cagr": round(cagr, 4),
        "volatility": round(vol, 4),
        "sharpe": round(sharpe, 4),
        "sortino": round(sortino, 4),
        "max_drawdown": round(max_dd, 4),
        "calmar": round(calmar, 4),
        "avg_turnover": round(avg_turnover, 4),
        "drawdown_series": drawdown_series,
    }


def _equal_weights(tickers: list[str]) -> dict[str, float]:
    n = len(tickers)
    return {t: 1.0 / n for t in tickers} if n > 0 else {}


def _pad_weights(w: dict[str, float], all_tickers: list[str]) -> dict[str, float]:
    padded = {t: float(w.get(t, 0.0)) for t in all_tickers}
    total = sum(padded.values())
    if total > 0:
        padded = {t: v / total for t, v in padded.items()}
    return padded


def run_backtest(
    prices: pd.DataFrame,
    tickers: list[str],
    asset_classes: list[str],
    constraints: Any,
    lookback_years: int,
    rebalance: str,
    risk_tolerance: float,
    cost_bps: float,
    use_ml: bool,
    use_regime: bool,
    regime_detector: Any,
    forecaster: Any,
    initial_value: float = 100000.0,
) -> dict:
    """
    Walk-forward backtest engine with no lookahead.

    Parameters
    ----------
    prices : pd.DataFrame
        Daily prices, DatetimeIndex, columns include tickers and optional SPY/NIFTYBEES.NS
    tickers : list[str]
        Portfolio tickers
    asset_classes : list[str]
        Asset class corresponding to each ticker in tickers
    constraints : dict or PortfolioConstraints
        Optimization constraints
    lookback_years : int
        Backtest window duration in years
    rebalance : str
        "weekly", "monthly", or "quarterly"
    risk_tolerance : float
        0.0 to 1.0
    cost_bps : float
        Turnover transaction cost in basis points
    use_ml : bool
        Enable ML forecaster views
    use_regime : bool
        Enable regime detector scaling
    regime_detector : RegimeDetector | None
    forecaster : ReturnForecaster | None
    initial_value : float
        Starting portfolio capital (default 100,000 INR)
    """
    rf = settings.RISK_FREE_RATE
    freq_days = REBALANCE_FREQ.get(rebalance, 21)

    core_tickers = [t for t in tickers if t in prices.columns]
    if not core_tickers:
        raise ValueError("None of the requested tickers exist in price history")

    asset_class_map = {t: asset_classes[tickers.index(t)] for t in core_tickers}

    spy_present = "SPY" in prices.columns
    nifty_present = "NIFTYBEES.NS" in prices.columns

    # Determine backtest start date
    total_days = len(prices)
    target_backtest_days = lookback_years * 252
    if total_days > target_backtest_days + 60:
        start_idx = total_days - target_backtest_days
    elif total_days > 120:
        start_idx = 60
    elif total_days > 30:
        start_idx = 20
    else:
        start_idx = max(1, total_days // 3)

    backtest_dates = prices.index[start_idx:]
    if len(backtest_dates) < 2:
        raise ValueError("Insufficient price data for backtest window")

    # Strategy tracking setup
    strategy_names = ["Optimized", "Equal Weight", "Buy and Hold", "Min Variance"]
    if spy_present:
        strategy_names.append("SPY")
    if nifty_present:
        strategy_names.append("NIFTY")

    # Equity series over time
    daily_values: dict[str, list[float]] = {s: [initial_value] for s in strategy_names}
    curve_dates: list = [backtest_dates[0]]

    current_values: dict[str, float] = {s: initial_value for s in strategy_names}
    current_weights: dict[str, dict[str, float]] = {s: {} for s in strategy_names}
    turnovers: dict[str, list[float]] = {s: [] for s in strategy_names}
    weights_history: list[dict] = []

    # Rebalance schedule indices relative to backtest_dates
    rebal_indices = list(range(0, len(backtest_dates), freq_days))
    if rebal_indices[-1] != len(backtest_dates) - 1:
        rebal_indices.append(len(backtest_dates) - 1)

    buy_hold_weights: dict[str, float] | None = None

    for step_i in range(len(rebal_indices) - 1):
        idx_curr = rebal_indices[step_i]
        idx_next = rebal_indices[step_i + 1]

        rebal_date = backtest_dates[idx_curr]

        # strictly NO LOOKAHEAD: slice data up to rebal_date only
        hist_prices = prices.loc[:rebal_date]

        # Identify valid tickers with sufficient history
        valid_tickers = [
            t for t in core_tickers
            if t in hist_prices.columns and hist_prices[t].dropna().shape[0] >= 20
        ]
        if not valid_tickers:
            valid_tickers = core_tickers

        valid_asset_classes = [asset_class_map[t] for t in valid_tickers]

        # Log returns up to rebal_date
        hist_subset = hist_prices[valid_tickers].ffill().dropna(how="all")
        window_returns = np.log(hist_subset / hist_subset.shift(1)).dropna()
        window_returns = window_returns.tail(settings.MVO_ROLLING_WINDOW_DAYS)

        # 1. Optimized weights
        opt_w: dict[str, float] = {}
        if len(window_returns) >= 15 and len(valid_tickers) >= 1:
            try:
                opt_res = optimize_from_returns(
                    returns_df=window_returns,
                    tickers=valid_tickers,
                    asset_classes=valid_asset_classes,
                    constraints=constraints,
                    risk_tolerance=risk_tolerance,
                    use_regime=use_regime,
                    regime_detector=regime_detector,
                    ml_forecasts=None,
                    use_ml=False,
                    risk_free_rate=rf,
                )
                opt_w = opt_res["weights"]
            except Exception as exc:
                logger.warning("Backtest optimizer fallback to equal weights at %s: %s", rebal_date, exc)
                opt_w = _equal_weights(valid_tickers)
        else:
            opt_w = _equal_weights(valid_tickers)

        # 2. Min Variance weights
        min_var_w: dict[str, float] = {}
        if len(window_returns) >= 15 and len(valid_tickers) >= 1:
            try:
                mv_res = optimize_from_returns(
                    returns_df=window_returns,
                    tickers=valid_tickers,
                    asset_classes=valid_asset_classes,
                    constraints=constraints,
                    risk_tolerance=0.0,
                    use_regime=use_regime,
                    regime_detector=regime_detector,
                    ml_forecasts=None,
                    use_ml=False,
                    risk_free_rate=rf,
                )
                min_var_w = mv_res["weights"]
            except Exception as exc:
                min_var_w = _equal_weights(valid_tickers)
        else:
            min_var_w = _equal_weights(valid_tickers)

        # 3. Equal Weight
        eq_w = _equal_weights(valid_tickers)

        # Pad weights across all core_tickers
        opt_padded = _pad_weights(opt_w, core_tickers)
        min_var_padded = _pad_weights(min_var_w, core_tickers)
        eq_padded = _pad_weights(eq_w, core_tickers)

        if buy_hold_weights is None:
            buy_hold_weights = opt_padded.copy()

        # Record weights history for Optimized
        rebal_date_str = str(rebal_date.date() if hasattr(rebal_date, "date") else rebal_date)
        hist_entry = {"date": rebal_date_str}
        hist_entry.update({t: round(opt_padded.get(t, 0.0), 4) for t in core_tickers})
        weights_history.append(hist_entry)

        # Target weights for each strategy
        step_weights = {
            "Optimized": opt_padded,
            "Equal Weight": eq_padded,
            "Buy and Hold": buy_hold_weights,
            "Min Variance": min_var_padded,
        }

        # Deduct turnover costs for portfolio strategies
        for strat, target_w in step_weights.items():
            prev_w = current_weights[strat]
            if prev_w and strat != "Buy and Hold":
                all_t = set(list(target_w.keys()) + list(prev_w.keys()))
                turnover = sum(abs(target_w.get(t, 0.0) - prev_w.get(t, 0.0)) for t in all_t) / 2.0
            elif not prev_w:
                # First allocation turnover: 0 cost from initial cash
                turnover = 0.0
            else:
                # Buy and hold doesn't rebalance
                turnover = 0.0

            turnovers[strat].append(turnover)
            cost = turnover * (cost_bps / 10000.0)
            current_values[strat] *= (1.0 - cost)
            current_weights[strat] = target_w

        # SPY and NIFTY turnover tracking
        if spy_present:
            turnovers["SPY"].append(0.0)
            current_weights["SPY"] = {"SPY": 1.0}
        if nifty_present:
            turnovers["NIFTY"].append(0.0)
            current_weights["NIFTY"] = {"NIFTYBEES.NS": 1.0}

        # Simulate daily performance from idx_curr to idx_next
        period_dates = backtest_dates[idx_curr: idx_next + 1]
        period_prices = prices.loc[period_dates]

        # Calculate daily percentage returns for each asset in this period
        daily_pct = period_prices.pct_change().fillna(0.0)

        # Advance each day in the interval
        for day_pos in range(1, len(period_dates)):
            day_dt = period_dates[day_pos]
            curve_dates.append(day_dt)

            # Core strategies
            for strat, w_dict in step_weights.items():
                day_ret = 0.0
                for t, w in w_dict.items():
                    if t in daily_pct.columns and w > 0:
                        r = float(daily_pct[t].iloc[day_pos])
                        if np.isfinite(r):
                            day_ret += w * r
                current_values[strat] *= (1.0 + day_ret)
                daily_values[strat].append(current_values[strat])

            # SPY
            if spy_present:
                r_spy = float(daily_pct["SPY"].iloc[day_pos]) if "SPY" in daily_pct.columns else 0.0
                if np.isfinite(r_spy):
                    current_values["SPY"] *= (1.0 + r_spy)
                daily_values["SPY"].append(current_values["SPY"])

            # NIFTY
            if nifty_present:
                r_nifty = float(daily_pct["NIFTYBEES.NS"].iloc[day_pos]) if "NIFTYBEES.NS" in daily_pct.columns else 0.0
                if np.isfinite(r_nifty):
                    current_values["NIFTY"] *= (1.0 + r_nifty)
                daily_values["NIFTY"].append(current_values["NIFTY"])

    # Build equity curves series
    equity_curves: dict[str, pd.Series] = {}
    metrics_by_strategy: dict[str, dict] = {}

    for strat in strategy_names:
        eq_series = pd.Series(daily_values[strat], index=curve_dates)
        equity_curves[strat] = eq_series
        metrics_by_strategy[strat] = _compute_metrics(
            eq_series, turnovers[strat], initial_value, rf,
        )

    years = max(len(curve_dates) / 252.0, 1.0 / 252.0)

    return {
        "equity_curves": equity_curves,
        "metrics": metrics_by_strategy,
        "weights_history": weights_history,
        "strategy_names": strategy_names,
        "years": round(years, 2),
        "dates": curve_dates,
    }
