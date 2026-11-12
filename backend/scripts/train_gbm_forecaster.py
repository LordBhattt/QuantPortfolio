"""Walk-forward GBM return forecaster training script.

Trains a cross-sectional HistGradientBoostingRegressor on a panel of ~23 tickers
using momentum, volatility, drawdown, RSI, volume, and market-return features.

Target: 21-day forward log return (vol-scaled).
Purge gap: 21 days between train end and first test date.

Saves:
  backend/models/ml_forecaster_v2.joblib  - (model, scaler) tuple
  backend/models/ml_forecaster_v2_meta.json - metadata with real OOS numbers

Usage:
  cd d:\\QuantPortfolio
  python backend/scripts/train_gbm_forecaster.py
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from scipy import stats
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.preprocessing import StandardScaler

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
CACHE_DIR = REPO_ROOT / "backend" / "data" / "cache"
MODELS_DIR = REPO_ROOT / "backend" / "models"
MODELS_DIR.mkdir(parents=True, exist_ok=True)

# Map ticker -> cache filename prefix (dots and hyphens replaced with _)
TICKERS = [
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "HINDUNILVR.NS",
    "ICICIBANK.NS", "KOTAKBANK.NS", "AXISBANK.NS", "BAJFINANCE.NS", "WIPRO.NS",
    "MARUTI.NS", "NESTLEIND.NS", "SPY", "QQQ", "GLD", "TLT",
    "BTC-USD", "ETH-USD", "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
]
MARKET_TICKER = "SPY"
FORWARD_DAYS = 21
PURGE_DAYS = 21
MIN_TRAIN_MONTHS = 18  # months before first OOS prediction
MONTHLY_STEP = 21  # ~1 month in trading days


def _cache_key(ticker: str) -> str:
    return ticker.replace(".", "_").replace("-", "-")


def load_cached_prices() -> dict[str, pd.DataFrame]:
    """Load all available cached parquet price files."""
    prices: dict[str, pd.DataFrame] = {}
    for ticker in TICKERS:
        key = _cache_key(ticker)
        matches = list(CACHE_DIR.glob(f"{key}_*.parquet"))
        if not matches:
            log.warning("No cache file for %s (key=%s)", ticker, key)
            continue
        df = pd.read_parquet(matches[0])
        if "close" not in df.columns and "Close" in df.columns:
            df = df.rename(columns={"Close": "close", "Open": "open",
                                    "High": "high", "Low": "low", "Volume": "volume"})
        df.index = pd.to_datetime(df.index)
        df = df.sort_index()
        prices[ticker] = df
        log.info("Loaded %s: %d rows", ticker, len(df))
    return prices


def _rsi(closes: pd.Series, period: int = 14) -> float:
    delta = closes.diff().dropna()
    gain = delta.clip(lower=0).rolling(period).mean().iloc[-1]
    loss = (-delta.clip(upper=0)).rolling(period).mean().iloc[-1]
    if loss == 0:
        return 100.0
    rs = gain / loss
    return float(100.0 - 100.0 / (1.0 + rs))


def build_features(closes: pd.Series, volumes: pd.Series | None, market_ret_21d: float) -> dict | None:
    """Build feature dict for a single asset at a single date.

    Uses data only up to the last row in closes.
    Returns None if insufficient history.
    """
    if len(closes) < 260:
        return None

    log_rets = np.log(closes / closes.shift(1)).dropna()

    def mom(skip: int, window: int) -> float:
        end = len(closes) - skip
        start = end - window
        if start < 0:
            return float("nan")
        return float(np.log(closes.iloc[end] / closes.iloc[start]))

    mom_1m = mom(5, 21)
    mom_3m = mom(5, 63)
    mom_6m = mom(5, 126)
    mom_12m = mom(5, 252)

    vol_21d = float(log_rets.tail(21).std() * np.sqrt(252))
    vol_63d = float(log_rets.tail(63).std() * np.sqrt(252))

    high_252 = float(closes.tail(252).max())
    cur = float(closes.iloc[-1])
    dd_252 = float(cur / high_252 - 1.0) if high_252 > 0 else 0.0

    rsi_val = _rsi(closes.tail(30), 14)

    if volumes is not None and len(volumes) >= 63:
        vol_mean = float(volumes.tail(63).mean())
        vol_std = float(volumes.tail(63).std())
        vol_z = float((volumes.iloc[-1] - vol_mean) / (vol_std + 1e-8))
        vol_z = float(np.clip(vol_z, -3.0, 3.0))
    else:
        vol_z = 0.0

    if any(np.isnan(v) for v in [mom_1m, mom_3m, mom_6m, mom_12m]):
        return None

    return {
        "mom_1m": mom_1m,
        "mom_3m": mom_3m,
        "mom_6m": mom_6m,
        "mom_12m": mom_12m,
        "vol_21d": vol_21d,
        "vol_63d": vol_63d,
        "drawdown_252d": dd_252,
        "rsi_14": rsi_val,
        "volume_zscore": vol_z,
        "market_return_21d": market_ret_21d,
    }


FEATURE_COLS = [
    "mom_1m", "mom_3m", "mom_6m", "mom_12m",
    "vol_21d", "vol_63d", "drawdown_252d",
    "rsi_14", "volume_zscore", "market_return_21d",
]


def build_panel(prices: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Build cross-sectional panel: (date, ticker, features..., target)."""
    market_df = prices.get(MARKET_TICKER)
    rows = []

    # Common date index
    all_dates: set = set()
    for df in prices.values():
        all_dates.update(df.index.tolist())
    sorted_dates = sorted(all_dates)

    # Resample to trading dates present in market data
    if market_df is not None:
        market_dates = sorted(market_df.index.tolist())
    else:
        market_dates = sorted_dates

    # Only use dates from 2018-01-01 onwards
    start_cut = pd.Timestamp("2018-01-01")
    market_dates = [d for d in market_dates if d >= start_cut]

    for i, date in enumerate(market_dates):
        # Need FORWARD_DAYS future data for target
        future_idx = i + FORWARD_DAYS
        if future_idx >= len(market_dates):
            break

        # Market return for feature
        if market_df is not None and i >= FORWARD_DAYS:
            past_market_idx = i - FORWARD_DAYS
            past_date = market_dates[past_market_idx]
            cur_market = market_df["close"].asof(date)
            past_market = market_df["close"].asof(past_date)
            if cur_market > 0 and past_market > 0:
                market_ret_21d = float(np.log(cur_market / past_market))
            else:
                market_ret_21d = 0.0
        else:
            market_ret_21d = 0.0

        future_date = market_dates[future_idx]

        for ticker, df in prices.items():
            closes_to_date = df["close"].loc[:date].dropna()
            if len(closes_to_date) < 260:
                continue

            volumes_to_date = df.get("volume", pd.Series(dtype=float)).loc[:date] if "volume" in df.columns else None

            feats = build_features(closes_to_date, volumes_to_date, market_ret_21d)
            if feats is None:
                continue

            # Target: 21d forward log return, vol-scaled
            cur_close = df["close"].asof(date)
            fut_close = df["close"].asof(future_date)
            if cur_close is None or fut_close is None or np.isnan(cur_close) or np.isnan(fut_close) or cur_close <= 0:
                continue

            fwd_ret = float(np.log(fut_close / cur_close))
            realized_vol = float(closes_to_date.pct_change().dropna().tail(21).std())
            if realized_vol > 0:
                fwd_ret_scaled = fwd_ret / (realized_vol + 1e-8)
            else:
                fwd_ret_scaled = fwd_ret

            row = {"date": date, "ticker": ticker, **feats, "target": fwd_ret_scaled}
            rows.append(row)

    panel = pd.DataFrame(rows)
    log.info("Panel built: %d rows, %d unique dates, %d unique tickers",
             len(panel), panel["date"].nunique(), panel["ticker"].nunique())
    return panel


def walk_forward_train_eval(panel: pd.DataFrame) -> tuple[object, object, list[float], list[float]]:
    """Walk-forward expanding-window training and OOS IC evaluation.

    Returns: (final_model, final_scaler, ic_series, baseline_ic_series)
    """
    dates = sorted(panel["date"].unique())
    n = len(dates)
    min_train = MIN_TRAIN_MONTHS * MONTHLY_STEP

    # Find first eval index
    first_eval_idx = min_train + PURGE_DAYS
    if first_eval_idx >= n:
        log.warning("Not enough dates for walk-forward eval")
        return None, None, [], []

    ic_list: list[float] = []
    base_ic_list: list[float] = []
    final_model = None
    final_scaler = None

    eval_indices = list(range(first_eval_idx, n, MONTHLY_STEP))
    log.info("Walk-forward: %d evaluation steps", len(eval_indices))

    for step, eval_idx in enumerate(eval_indices):
        # Train on dates[:eval_idx - PURGE_DAYS]
        train_cut = eval_idx - PURGE_DAYS
        train_dates = set(dates[:train_cut])
        eval_date = dates[eval_idx]

        train_df = panel[panel["date"].isin(train_dates)]
        test_df = panel[panel["date"] == eval_date]

        if len(train_df) < 50 or len(test_df) < 3:
            continue

        X_train = train_df[FEATURE_COLS].values
        y_train = train_df["target"].values
        X_test = test_df[FEATURE_COLS].values
        y_test = test_df["target"].values

        scaler = StandardScaler()
        X_train_sc = scaler.fit_transform(X_train)
        X_test_sc = scaler.transform(X_test)

        model = HistGradientBoostingRegressor(
            max_iter=100, max_depth=4, random_state=42, min_samples_leaf=10,
        )
        model.fit(X_train_sc, y_train)

        preds = model.predict(X_test_sc)

        # Spearman IC
        if len(preds) >= 3:
            ic, _ = stats.spearmanr(preds, y_test)
            if np.isfinite(ic):
                ic_list.append(float(ic))

        # Baseline IC (class-prior: predict 0 for all)
        base_preds = np.zeros(len(y_test))
        base_ic, _ = stats.spearmanr(base_preds, y_test)
        if np.isfinite(base_ic):
            base_ic_list.append(float(base_ic))

        # Keep final model (last step)
        final_model = model
        final_scaler = scaler

        if step % 10 == 0:
            mean_ic = np.mean(ic_list) if ic_list else float("nan")
            log.info("Step %d/%d (date=%s): running IC=%.4f",
                     step + 1, len(eval_indices), eval_date.strftime("%Y-%m"), mean_ic)

    return final_model, final_scaler, ic_list, base_ic_list


def main() -> None:
    log.info("Loading cached prices ...")
    prices = load_cached_prices()
    if len(prices) < 5:
        log.error("Too few tickers loaded (%d). Abort.", len(prices))
        sys.exit(1)

    log.info("Building panel ...")
    panel = build_panel(prices)
    if len(panel) < 200:
        log.error("Panel too small (%d rows). Abort.", len(panel))
        sys.exit(1)

    log.info("Walk-forward training ...")
    model, scaler, ic_series, base_ic_series = walk_forward_train_eval(panel)

    if not ic_series:
        log.error("No IC values computed. Training failed.")
        sys.exit(1)

    oos_mean_ic = float(np.mean(ic_series))
    oos_ic_std = float(np.std(ic_series))
    n_steps = len(ic_series)
    ic_tstat = float(oos_mean_ic / (oos_ic_std / np.sqrt(n_steps))) if oos_ic_std > 0 else 0.0
    baseline_ic = float(np.mean(base_ic_series)) if base_ic_series else 0.0

    gate_passed = oos_mean_ic > 0.02 and abs(ic_tstat) > 2.0

    print("\n" + "=" * 60)
    print(f"GBM FORECASTER WALK-FORWARD RESULTS")
    print("=" * 60)
    print(f"  OOS eval steps  : {n_steps}")
    print(f"  OOS mean IC     : {oos_mean_ic:.4f}")
    print(f"  IC std          : {oos_ic_std:.4f}")
    print(f"  IC t-stat       : {ic_tstat:.2f}")
    print(f"  Baseline IC     : {baseline_ic:.4f}")
    print(f"  Gate            : IC > 0.02 AND |t-stat| > 2")
    if gate_passed:
        print(f"  Result          : GATE PASSED - model ENABLED by default")
    else:
        print(f"  Result          : GATE NOT PASSED - model DISABLED by default")
        print(f"                    (use_ml_forecast will not activate GBM)")
    print("=" * 60 + "\n")

    # Save model
    out_path = MODELS_DIR / "ml_forecaster_v2.joblib"
    joblib.dump((model, scaler), out_path)
    log.info("Saved model to %s", out_path)

    # Save metadata
    import datetime
    meta = {
        "model_kind": "gbm",
        "train_end_date": datetime.date.today().isoformat(),
        "oos_mean_ic": oos_mean_ic,
        "oos_ic_tstat": ic_tstat,
        "oos_ic_std": oos_ic_std,
        "baseline_ic": baseline_ic,
        "n_eval_steps": n_steps,
        "gate_passed": gate_passed,
        "feature_names": FEATURE_COLS,
        "universe_size": len(prices),
    }
    meta_path = MODELS_DIR / "ml_forecaster_v2_meta.json"
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)
    log.info("Saved metadata to %s", meta_path)


if __name__ == "__main__":
    main()
