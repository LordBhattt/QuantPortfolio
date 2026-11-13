"""Evaluate QP Smart candidates with a strict train/test split.

Usage:
    python backend/scripts/improvement_evaluation.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.config import get_settings
from backend.quant.backtest import _compute_metrics, _static_candidate_score
from backend.quant.smart_backtest import (
    candidate_configs,
    select_config_rolling,
    smart_weights,
    vol_model_error,
)
from backend.schemas.optimization import PortfolioConstraints
from backend.services.optimization_service import optimize_from_returns

settings = get_settings()
CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "cache"
INITIAL_VALUE = 100_000.0
TICKER_CLASSES = {
    "RELIANCE.NS": "stock",
    "BTC-USD": "crypto",
    "GLD": "gold",
    "GOLDBEES.NS": "gold",
    "NIFTYBEES.NS": "mf_etf",
    "HDFCBANK.NS": "stock",
    "LTGILTDIR.NS": "bond",
    "TCS.NS": "stock",
}
PROXY_TICKERS = {"LTGILTDIR.NS": "TLT"}


def load_prices() -> pd.DataFrame:
    series: dict[str, pd.Series] = {}
    for ticker in [*TICKER_CLASSES, "SPY"]:
        stem = ticker.replace(".", "_")
        matches = sorted(CACHE_DIR.glob(f"{stem}_*.parquet"))
        if matches:
            frame = pd.read_parquet(matches[-1])
        else:
            source = PROXY_TICKERS.get(ticker, ticker)
            frame = yf.download(
                source,
                start="2018-01-01",
                end=pd.Timestamp.utcnow().date().isoformat(),
                auto_adjust=True,
                progress=False,
            )
            if frame.empty:
                raise RuntimeError(f"No five-year history available for {ticker} (source {source})")
            if isinstance(frame.columns, pd.MultiIndex):
                frame.columns = frame.columns.get_level_values(0)
            frame.index.name = "date"
            frame.to_parquet(CACHE_DIR / f"{stem}_2018-current.parquet")
        column = "close" if "close" in frame.columns else frame.columns[0]
        index = pd.to_datetime(frame.index)
        if index.tz is not None:
            index = index.tz_localize(None)
        series[ticker] = pd.Series(frame[column].to_numpy(dtype=float), index=index)
    prices = pd.DataFrame(series).sort_index().ffill()
    prices = prices.dropna()
    missing = [ticker for ticker in TICKER_CLASSES if ticker not in prices or prices[ticker].isna().any()]
    if missing:
        raise RuntimeError(f"Five-year history has gaps for: {', '.join(missing)}")
    return prices.dropna(how="all")


def _optimizer(frame: pd.DataFrame, tickers: list[str], classes: list[str], constraints: PortfolioConstraints) -> dict[str, float]:
    result = optimize_from_returns(
        returns_df=frame,
        tickers=tickers,
        asset_classes=classes,
        constraints=constraints,
        risk_tolerance=0.5,
        use_regime=False,
        regime_detector=None,
        ml_forecasts=None,
        use_ml=False,
    )
    return result["weights"]


def simulate(
    prices: pd.DataFrame,
    tickers: list[str],
    classes: list[str],
    constraints: PortfolioConstraints,
    config_name: str,
    train_end: pd.Timestamp,
) -> dict:
    configs = {config.label(): config for config in candidate_configs()}
    config = configs.get(config_name)
    if config is None:
        raise ValueError(f"Unknown candidate: {config_name}")
    test_prices = prices.loc[train_end:].copy()
    returns = np.log(prices[tickers].ffill() / prices[tickers].ffill().shift(1)).dropna()
    current = INITIAL_VALUE
    equity = [current]
    turnovers: list[float] = []
    previous: dict[str, float] | None = None
    test_dates = test_prices.index
    schedule = range(0, len(test_dates) - 1, config.rebalance_days)
    vol_models = None
    for index in schedule:
        date = test_dates[index]
        history = returns.loc[:date].tail(settings.MVO_ROLLING_WINDOW_DAYS)
        if len(history) < 30:
            continue
        current_weights = smart_weights(
            history,
            tickers,
            classes,
            constraints,
            config,
            lambda frame, names, asset_classes: _optimizer(frame, names, asset_classes, constraints),
            previous_weights=previous,
            vol_models=vol_models,
        )
        turnover = (
            sum(abs(current_weights[t] - previous.get(t, 0.0)) for t in tickers) / 2.0
            if previous
            else 0.0
        )
        turnovers.append(turnover)
        current *= 1.0 - turnover * 10 / 10000
        next_index = min(index + config.rebalance_days, len(test_dates) - 1)
        period = test_prices.iloc[index:next_index + 1][tickers].pct_change().fillna(0.0)
        for _, row in period.iloc[1:].iterrows():
            current *= 1.0 + float(sum(current_weights[t] * row[t] for t in tickers))
            equity.append(current)
        previous = current_weights
    curve = pd.Series(equity, index=pd.date_range(test_dates[0], periods=len(equity), freq="B"))
    metrics = _compute_metrics(curve, turnovers, INITIAL_VALUE, settings.RISK_FREE_RATE)
    metrics["_daily_returns"] = curve.pct_change().dropna()
    return metrics


def bootstrap_sharpe_difference(
    selected_returns: pd.Series,
    equal_returns: pd.Series,
    samples: int = 1000,
    block_size: int = 21,
) -> dict[str, float | bool]:
    differences = (selected_returns - equal_returns).dropna().to_numpy()
    if len(differences) < block_size:
        return {"lower": 0.0, "upper": 0.0, "mean": 0.0, "significant": False}
    rng = np.random.default_rng(42)
    blocks = [
        differences[index:index + block_size]
        for index in range(len(differences) - block_size + 1)
    ]
    values = []
    for _ in range(samples):
        draw = np.concatenate([blocks[rng.integers(len(blocks))] for _ in range(len(differences) // block_size + 1)])
        values.append(float(draw[:len(differences)].mean() * np.sqrt(252)))
    lower, upper = np.quantile(values, [0.025, 0.975])
    return {
        "lower": float(lower),
        "upper": float(upper),
        "mean": float(np.mean(values)),
        "significant": bool(lower > 0 or upper < 0),
    }


def write_report(
    prices: pd.DataFrame,
    split: pd.Timestamp,
    selected: str,
    heldout: dict[str, dict],
    rolling: list[tuple[str, str, dict]],
    vol_error: dict[str, float],
    bootstrap: dict[str, float | bool],
) -> Path:
    report_path = Path(__file__).resolve().parents[2] / "docs" / "IMPROVEMENT_REPORT.md"
    lines = [
        "# QP Smart Improvement Report",
        "",
        "Selection uses four expanding windows ending before the cutoff. The score is mean",
        "train Sharpe minus 0.25 times its cross-window standard deviation. The final 40%",
        "is never read by selection. All candidates use the same class constraints and 10 bps cost.",
        "",
        f"Data: {prices.index[0].date()} to {prices.index[-1].date()} ({len(prices)} rows).",
        f"Train cutoff: {split.date()}. Selected configuration: **{selected}**.",
        "SPY is a reference benchmark only and is not constrained across five asset classes.",
        "The LTGILTDIR.NS bond history uses the documented TLT proxy.",
        "",
        "## Held-out final 40%",
        "",
        "| Candidate | Profit (INR) | Sharpe | Max drawdown | Turnover |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, metrics in heldout.items():
        lines.append(
            f"| {name} | {metrics['total_profit_inr']:,.2f} | {metrics['sharpe']:.4f} | "
            f"{metrics['max_drawdown']:.2%} | {metrics['avg_turnover']:.4f} |"
        )
    lines.extend([
        "",
        "## Rolling out-of-sample windows",
        "",
        "| Start | Selected config | Profit (INR) | Sharpe | Max drawdown | Turnover |",
        "|---|---|---:|---:|---:|---:|",
    ])
    for start, config, metrics in rolling:
        lines.append(
            f"| {start} | {config} | {metrics['total_profit_inr']:,.2f} | {metrics['sharpe']:.4f} | "
            f"{metrics['max_drawdown']:.2%} | {metrics['avg_turnover']:.4f} |"
        )
    if rolling:
        lines.extend([
            "",
            f"Rolling average: profit INR {np.mean([m['total_profit_inr'] for _, _, m in rolling]):,.2f}, "
            f"Sharpe {np.mean([m['sharpe'] for _, _, m in rolling]):.4f}, "
            f"max drawdown {np.mean([m['max_drawdown'] for _, _, m in rolling]):.2%}, "
            f"turnover {np.mean([m['avg_turnover'] for _, _, m in rolling]):.4f}.",
        ])
    lines.extend([
        "",
        "## Model and strategy findings",
        "",
        f"Volatility model MAE was {vol_error['model_mae']:.4f} versus "
        f"{vol_error['baseline_mae']:.4f} for trailing volatility, so it remains disabled.",
        f"Block-bootstrap annualized return-difference CI versus equal weight: "
        f"[{bootstrap['lower']:.4f}, {bootstrap['upper']:.4f}], "
        f"significant={bootstrap['significant']}.",
        "QP Smart is promoted only from train-window evidence. No held-out result is used to change settings.",
        "No bootstrap Sharpe difference is claimed until the comparison is implemented over the same daily curves.",
        "",
    ])
    report_path.write_text("\n".join(lines), encoding="utf-8")
    return report_path


def main() -> None:
    prices = load_prices()
    tickers = [ticker for ticker in TICKER_CLASSES if ticker in prices.columns]
    classes = [TICKER_CLASSES[ticker] for ticker in tickers]
    constraints = PortfolioConstraints(
        stocks={"min": 0.10, "max": 0.50},
        crypto={"min": 0.05, "max": 0.20},
        gold={"min": 0.05, "max": 0.20},
        mf_etf={"min": 0.05, "max": 0.30},
        bonds={"min": 0.10, "max": 0.30},
    )
    split = prices.index[int(len(prices) * 0.60)]
    train = prices.loc[:split, tickers]
    selected, scores = select_config_rolling(
        train,
        split,
        lambda config, data: _static_candidate_score(
            config, data, tickers, classes, constraints, 0.5, False, None, settings.RISK_FREE_RATE
        ),
    )
    print(f"DATA {prices.index[0].date()} to {prices.index[-1].date()} ({len(prices)} rows)")
    print(f"TRAIN through {split.date()} | TEST {prices.index[prices.index > split][0].date()} onward")
    print(f"SELECTED {selected.label()}")
    print("TRAIN SCORES")
    for name, score in sorted(scores.items(), key=lambda item: item[1], reverse=True):
        print(f"{name}\t{score:.4f}")
    heldout_metrics: dict[str, dict] = {}
    print("HELD-OUT")
    for config in candidate_configs():
        metrics = simulate(prices, tickers, classes, constraints, config.label(), split)
        heldout_metrics[config.label()] = metrics
        print(
            f"{config.label()}\tprofit={metrics['total_profit_inr']:.2f}"
            f"\tsharpe={metrics['sharpe']:.4f}\tmax_dd={metrics['max_drawdown']:.4f}"
            f"\tturnover={metrics['avg_turnover']:.4f}"
        )
    if "SPY" in prices:
        spy = prices.loc[split:, "SPY"].dropna()
        spy_equity = INITIAL_VALUE * spy / spy.iloc[0]
        heldout_metrics["SPY reference"] = _compute_metrics(
            spy_equity, [], INITIAL_VALUE, settings.RISK_FREE_RATE
        )
        print(f"SPY\tprofit={heldout_metrics['SPY reference']['total_profit_inr']:.2f}")
    returns = np.log(prices[tickers].ffill() / prices[tickers].ffill().shift(1)).dropna()
    volatility_error = vol_model_error(returns.loc[:split], returns.loc[returns.index > split])
    print("VOL_ERROR", volatility_error)

    rolling_starts = [0, 126, 252, 378, 504]
    rolling_results = []
    rolling_rows: list[tuple[str, str, dict]] = []
    print("ROLLING_QP_SMART")
    for start in rolling_starts:
        window = prices.iloc[start:start + 1260]
        if len(window) < 800:
            continue
        window_split = window.index[int(len(window) * 0.60)]
        selected_window, _ = select_config_rolling(
            window.loc[:window_split, tickers],
            window_split,
            lambda config, data: _static_candidate_score(
                config, data, tickers, classes, constraints, 0.5, False, None, settings.RISK_FREE_RATE
            ),
        )
        metrics = simulate(window, tickers, classes, constraints, selected_window.label(), window_split)
        rolling_results.append(metrics)
        rolling_rows.append((str(window.index[0].date()), selected_window.label(), metrics))
        print(
            f"{window.index[0].date()}\t{selected_window.label()}"
            f"\tprofit={metrics['total_profit_inr']:.2f}\tsharpe={metrics['sharpe']:.4f}"
            f"\tmax_dd={metrics['max_drawdown']:.4f}"
        )
    if rolling_results:
        print(
            "ROLLING_AVERAGE"
            f"\tprofit={np.mean([m['total_profit_inr'] for m in rolling_results]):.2f}"
            f"\tsharpe={np.mean([m['sharpe'] for m in rolling_results]):.4f}"
            f"\tmax_dd={np.mean([m['max_drawdown'] for m in rolling_results]):.4f}"
            f"\tturnover={np.mean([m['avg_turnover'] for m in rolling_results]):.4f}"
        )
    selected_returns = heldout_metrics[selected.label()]["_daily_returns"]
    equal_returns = heldout_metrics["Shrinkage, lambda=0"]["_daily_returns"]
    bootstrap = bootstrap_sharpe_difference(selected_returns, equal_returns)
    print("BOOTSTRAP", bootstrap)
    report_path = write_report(
        prices, split, selected.label(), heldout_metrics, rolling_rows, volatility_error, bootstrap
    )
    print(f"REPORT {report_path}")


if __name__ == "__main__":
    main()
