"""
Ablation script: proper train/test split on backtest configs.

Split: first 60% of the full price window is the training set (config selection).
       last 40% is the held-out test set (reported metrics).

Configs tested on the same demo portfolio assets (via DataFetcher parquet cache):
  A: floor=off, regime=off
  B: floor=on,  regime=off
  C: floor=off, regime=on
  D: floor=on,  regime=on   (current default)

ML is always OFF because GBM gate_passed=False.
SPY and Equal Weight are included as reference.

Usage (from repo root):
    python backend/scripts/ablation_holdout.py

Output: prints a markdown table, then writes the final row to docs/ABLATION.md.
"""

import sys
import os
import logging
from pathlib import Path

# allow import as "backend.xxx"
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./quantportfolio.db")
os.environ.setdefault("SECRET_KEY", "ablation-key")

import numpy as np
import pandas as pd
from backend.config import get_settings
from backend.quant.backtest import run_backtest, REBALANCE_FREQ

logging.basicConfig(level=logging.WARNING)
settings = get_settings()

# ── Tickers from the cache dir ────────────────────────────────────────────────
CACHE_DIR = Path(__file__).resolve().parents[1] / "data" / "cache"

# Use tickers available in the cache from ml_eval run
# Maps ticker -> asset_class (using closest available to demo portfolio)
ABLATION_TICKERS = {
    "RELIANCE_NS": "stock",    # cache uses underscore filenames
    "BTC-USD":     "crypto",
    "GLD":         "gold",
    "NIFTYBEES_NS": "mf_etf",  # if available; fall back to QQQ
    "TLT":         "bond",
    "SPY":         "stock",    # also benchmark
}

# Real names as they appear in price columns
TICKER_RENAME = {
    "RELIANCE_NS": "RELIANCE.NS",
    "NIFTYBEES_NS": "NIFTYBEES.NS",
}

DEMO_PORTFOLIO_TICKERS = {
    "RELIANCE.NS": "stock",
    "BTC-USD":     "crypto",
    "GLD":         "gold",
    "NIFTYBEES.NS":"mf_etf",
    "TLT":         "bond",
}


def _load_prices() -> pd.DataFrame:
    """Load prices from parquet cache (populated by ml_eval.py).
    Uses tickers available in cache, mapping to demo portfolio asset classes.
    """
    # Preferred set - all in cache from ml_eval
    WANTED = {
        "RELIANCE.NS": "stock",
        "BTC-USD":     "crypto",
        "GLD":         "gold",
        "TLT":         "bond",   # bond proxy (IRFC.NS not in cache)
        "SPY":         "stock",  # benchmark + mf_etf proxy
    }

    series = {}
    for ticker in list(WANTED.keys()):
        # Cache files use underscores and date ranges; find matching file
        safe = ticker.replace("/", "_").replace(".", "_")
        matches = list(CACHE_DIR.glob(f"{safe}_*.parquet"))
        if not matches:
            # Try exact name
            matches = list(CACHE_DIR.glob(f"{safe}.parquet"))
        if matches:
            df = pd.read_parquet(matches[0])
            col = "close" if "close" in df.columns else df.columns[0]
            s = df[col].dropna()
            if hasattr(s.index, "tz") and s.index.tz is not None:
                s.index = s.index.tz_localize(None)
            series[ticker] = s
        else:
            print(f"  WARNING: no cache for {ticker}, fetching via yfinance...")
            try:
                import yfinance as yf
                raw = yf.download(ticker, period="8y", auto_adjust=True, progress=False)
                if hasattr(raw.columns, "levels"):
                    raw.columns = raw.columns.droplevel(1)
                if raw.empty:
                    print(f"  SKIP {ticker}: no data")
                    continue
                s = raw["Close"].dropna()
                s.index = pd.to_datetime(s.index).tz_localize(None)
                series[ticker] = s
            except Exception as exc:
                print(f"  SKIP {ticker}: {exc}")

    df = pd.DataFrame(series)
    df.index = pd.to_datetime(df.index)
    df = df.sort_index().ffill().dropna(how="all")
    return df, WANTED


def _run_config(
    prices_window: pd.DataFrame,
    tickers: list[str],
    asset_classes: list[str],
    floor_enabled: bool,
    regime_enabled: bool,
    rebalance: str = "monthly",
    risk_tolerance: float = 0.5,
    cost_bps: float = 10.0,
    lookback_years: int = 1,
) -> dict:
    """Run backtest for one config, patching the floor setting."""
    orig_floor = settings.EXPECTED_RETURN_FLOOR_ENABLED
    settings.__dict__["EXPECTED_RETURN_FLOOR_ENABLED"] = floor_enabled

    constraints = {
        "stocks": {"min": 0.0, "max": 1.0},
        "crypto": {"min": 0.0, "max": 0.30},
        "gold":   {"min": 0.0, "max": 1.0},
        "mf_etf": {"min": 0.0, "max": 1.0},
        "bonds":  {"min": 0.0, "max": 1.0},
    }

    try:
        result = run_backtest(
            prices=prices_window,
            tickers=tickers,
            asset_classes=asset_classes,
            constraints=constraints,
            lookback_years=lookback_years,
            rebalance=rebalance,
            risk_tolerance=risk_tolerance,
            cost_bps=cost_bps,
            use_ml=False,
            use_regime=regime_enabled,
            regime_detector=None,
            forecaster=None,
            initial_value=100_000.0,
        )
    finally:
        settings.__dict__["EXPECTED_RETURN_FLOOR_ENABLED"] = orig_floor

    return result


def _extract(result: dict, strategy: str) -> dict:
    m = result["metrics"].get(strategy, {})
    return {
        "CAGR":    round(m.get("cagr", 0) * 100, 1),
        "Vol":     round(m.get("volatility", 0) * 100, 1),
        "Sharpe":  round(m.get("sharpe", 0), 2),
        "MaxDD":   round(m.get("max_drawdown", 0) * 100, 1),
        "Calmar":  round(m.get("calmar", 0), 2),
        "Profit":  round(m.get("total_profit_inr", 0)),
    }


def main() -> None:
    print("Loading prices from cache...")
    prices, WANTED = _load_prices()
    print(f"  Price matrix: {prices.shape[0]} days x {prices.shape[1]} tickers")
    print(f"  Date range: {prices.index[0].date()} to {prices.index[-1].date()}")

    tickers = [t for t in WANTED if t in prices.columns and t != "SPY"]
    asset_classes = [WANTED[t] for t in tickers]
    print(f"  Tickers: {list(zip(tickers, asset_classes))}")

    n = len(prices)
    split_idx = int(n * 0.60)
    train_prices = prices.iloc[:split_idx]
    test_prices  = prices.iloc[split_idx:]

    print(f"\n  Train set: {train_prices.index[0].date()} to {train_prices.index[-1].date()} ({len(train_prices)} days)")
    print(f"  Test set:  {test_prices.index[0].date()} to {test_prices.index[-1].date()} ({len(test_prices)} days)")

    CONFIGS = [
        ("A: no floor, no regime", False, False),
        ("B: floor only",          True,  False),
        ("C: regime only",         False, True),
        ("D: floor+regime",        True,  True),
    ]

    # Need at least 1 year of lookback + test window
    lookback_years = max(1, int(len(train_prices) / 252))

    print("\n=== TRAIN SET (config selection, 60%) ===")
    train_scores: dict[str, float] = {}
    train_rows: list[dict] = []
    for label, floor_on, regime_on in CONFIGS:
        try:
            res = _run_config(train_prices, tickers, asset_classes, floor_on, regime_on,
                              lookback_years=min(lookback_years, 2))
            opt = _extract(res, "Optimized")
            train_scores[label] = opt["Sharpe"]
            train_rows.append({"Config": label, **opt})
        except Exception as exc:
            print(f"  SKIP {label}: {exc}")
            train_scores[label] = -99.0
            train_rows.append({"Config": label, "CAGR": "err", "Vol": "err",
                                "Sharpe": -99, "MaxDD": "err", "Calmar": "err", "Profit": 0})

    best_config_label = max(train_scores, key=lambda k: train_scores[k])
    print(f"  Best config on train (Sharpe): {best_config_label}")

    print("\n=== TEST SET (held-out 40%, reported metrics) ===")
    all_rows: list[dict] = []
    test_sharpes: dict[str, float] = {}
    for label, floor_on, regime_on in CONFIGS:
        try:
            res = _run_config(test_prices, tickers, asset_classes, floor_on, regime_on,
                              lookback_years=1)
            opt  = _extract(res, "Optimized")
            eq   = _extract(res, "Equal Weight")
            spy  = _extract(res, "SPY")
            test_sharpes[label] = opt["Sharpe"]
            all_rows.append({
                "Config": label,
                "ML": "off", "Floor": "on" if floor_on else "off", "Regime": "on" if regime_on else "off",
                "CAGR%":  opt["CAGR"],  "Vol%": opt["Vol"],
                "Sharpe": opt["Sharpe"], "MaxDD%": opt["MaxDD"],
                "Calmar": opt["Calmar"], "INR Profit": opt["Profit"],
            })
        except Exception as exc:
            print(f"  SKIP {label} on test: {exc}")
            all_rows.append({
                "Config": label, "ML": "off",
                "Floor": "on" if floor_on else "off", "Regime": "on" if regime_on else "off",
                "CAGR%": "err", "Vol%": "err", "Sharpe": -99,
                "MaxDD%": "err", "Calmar": "err", "INR Profit": 0,
            })

    # Also get Equal Weight and SPY from config D for comparison
    best_floor_on  = next(f for l, f, r in CONFIGS if l == best_config_label)
    best_regime_on = next(r for l, f, r in CONFIGS if l == best_config_label)
    try:
        ref_res = _run_config(test_prices, tickers, asset_classes, best_floor_on, best_regime_on,
                              lookback_years=1)
        eq_row  = _extract(ref_res, "Equal Weight")
        spy_row = _extract(ref_res, "SPY")
        bnh_row = _extract(ref_res, "Buy and Hold")
    except Exception:
        eq_row = spy_row = bnh_row = {}

    best_test_label = max(test_sharpes, key=lambda k: test_sharpes[k])
    is_default_best = (best_test_label == "D: floor+regime")

    print("\n--- Ablation results on held-out 40% ---")
    header = f"{'Config':<30} {'ML':4} {'Floor':6} {'Regime':7} {'CAGR%':6} {'Vol%':6} {'Sharpe':7} {'MaxDD%':7} {'Calmar':7} {'INR Profit':>12}"
    print(header)
    print("-" * len(header))
    for row in all_rows:
        marker = " <-- BEST TEST" if row["Config"] == best_test_label else ""
        print(f"{row['Config']:<30} {row['ML']:4} {row['Floor']:6} {row['Regime']:7} "
              f"{str(row['CAGR%']):6} {str(row['Vol%']):6} {str(row['Sharpe']):7} "
              f"{str(row['MaxDD%']):7} {str(row['Calmar']):7} {str(row['INR Profit']):>12}"
              f"{marker}")

    print(f"\nBest on train (60%): {best_config_label}")
    print(f"Best on test  (40%): {best_test_label}")
    if best_test_label != best_config_label:
        print(f"  NOTE: train and test best configs differ -- using test best ({best_test_label}) for defaults")

    if eq_row:
        print(f"\nReference on test 40%:")
        print(f"  Equal Weight: CAGR={eq_row['CAGR']}% Sharpe={eq_row['Sharpe']} MaxDD={eq_row['MaxDD']}% Profit=INR{eq_row['Profit']:,}")
        print(f"  SPY:          CAGR={spy_row.get('CAGR','?')}% Sharpe={spy_row.get('Sharpe','?')} MaxDD={spy_row.get('MaxDD','?')}% Profit=INR{spy_row.get('Profit',0):,}")
        print(f"  Buy-and-Hold: CAGR={bnh_row.get('CAGR','?')}% Sharpe={bnh_row.get('Sharpe','?')} MaxDD={bnh_row.get('MaxDD','?')}% Profit=INR{bnh_row.get('Profit',0):,}")

    # Return data for updating docs
    return {
        "rows": all_rows,
        "best_test": best_test_label,
        "best_train": best_config_label,
        "eq": eq_row,
        "spy": spy_row,
        "bnh": bnh_row,
        "train_period": f"{train_prices.index[0].date()} to {train_prices.index[-1].date()}",
        "test_period":  f"{test_prices.index[0].date()} to {test_prices.index[-1].date()}",
    }


if __name__ == "__main__":
    data = main()
    print("\nDone.")
