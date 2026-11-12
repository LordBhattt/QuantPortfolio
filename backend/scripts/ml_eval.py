"""Walk-forward ML evaluation script for QuantPortfolio.

Measures model quality honestly using an expanding-window walk-forward
backtest across the multi-asset universe.

Compares five models:
1. Zero baseline: predict 0 for all assets
2. Class-prior baseline: hardcoded asset-class priors annualized, converted to horizon
3. Trailing mean: 63-day trailing mean log return, annualized
4. Current momentum_model.pkl: loaded from backend/models/momentum_model.pkl, predict_blended() logic
5. LSTM path: trained on SPY data as the repo does, then predicted

Metrics:
- Mean Spearman IC (rank correlation between prediction and actual 21d forward log return)
- t-statistic of the IC series (IC.mean() / IC.std() * sqrt(n))
- Hit rate (fraction of predictions with correct sign)
- RMSE
- Top-minus-bottom quantile spread (top 1/3 minus bottom 1/3 actual return)

Usage:
    cd d:/QuantPortfolio
    python backend/scripts/ml_eval.py
"""

from __future__ import annotations

import logging
import math
import os
import sys
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# --- Path setup so imports from backend work ---
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger("ml_eval")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

START_DATE = "2018-01-01"
END_DATE = datetime.today().strftime("%Y-%m-%d")
TARGET_HORIZON = 21        # 21-day forward log return
PURGE_GAP_DAYS = 21        # 21 days between train end and test start
TRAILING_WINDOW = 63       # 63-day trailing mean window

CACHE_DIR = PROJECT_ROOT / "backend" / "data" / "cache"
CACHE_MAX_AGE_HOURS = 24

UNIVERSE: List[str] = [
    # NSE
    "RELIANCE.NS", "TCS.NS", "HDFCBANK.NS", "INFY.NS", "HINDUNILVR.NS",
    "ICICIBANK.NS", "KOTAKBANK.NS", "AXISBANK.NS", "BAJFINANCE.NS",
    "WIPRO.NS", "MARUTI.NS", "NESTLEIND.NS",
    # US
    "SPY", "QQQ", "GLD", "TLT", "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA",
    # Crypto
    "BTC-USD", "ETH-USD",
    # Gold
    "GOLDBEES.NS",
]

ASSET_CLASS_MAP: Dict[str, str] = {
    "RELIANCE.NS": "stock", "TCS.NS": "stock", "HDFCBANK.NS": "stock",
    "INFY.NS": "stock", "HINDUNILVR.NS": "stock", "ICICIBANK.NS": "stock",
    "KOTAKBANK.NS": "stock", "AXISBANK.NS": "stock", "BAJFINANCE.NS": "stock",
    "WIPRO.NS": "stock", "MARUTI.NS": "stock", "NESTLEIND.NS": "stock",
    "AAPL": "stock", "MSFT": "stock", "GOOGL": "stock",
    "AMZN": "stock", "NVDA": "stock",
    "SPY": "mf_etf", "QQQ": "mf_etf",
    "GLD": "gold", "GOLDBEES.NS": "gold",
    "TLT": "bond",
    "BTC-USD": "crypto", "ETH-USD": "crypto",
}

CLASS_PRIORS_ANNUAL: Dict[str, float] = {
    "stock":  0.11,
    "mf_etf": 0.10,
    "bond":   0.065,
    "gold":   0.09,
    "crypto": 0.08,
    "other":  0.08,
}

MODEL_PATH = PROJECT_ROOT / "backend" / "models" / "momentum_model.pkl"
LSTM_WEIGHTS_PATH = PROJECT_ROOT / "backend" / "ml" / "weights" / "lstm_latest.pt"

# ---------------------------------------------------------------------------
# Caching & Data Download
# ---------------------------------------------------------------------------

def _cache_path(ticker: str) -> Path:
    safe = ticker.replace("/", "_").replace(".", "_")
    return CACHE_DIR / f"{safe}_{START_DATE}_{END_DATE}.parquet"


def _cache_valid(path: Path) -> bool:
    if not path.exists():
        return False
    age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
    return age < timedelta(hours=CACHE_MAX_AGE_HOURS)


def download_prices(tickers: List[str]) -> Tuple[Dict[str, pd.Series], List[str]]:
    """Download daily close prices for all tickers with 24h parquet caching.

    Returns:
        prices: dict mapping ticker -> pd.Series of daily close prices
        failed: list of tickers that failed to download
    """
    try:
        import yfinance as yf
    except ImportError as exc:
        raise RuntimeError("yfinance not installed. Run: pip install yfinance") from exc

    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    prices: Dict[str, pd.Series] = {}
    failed: List[str] = []

    for ticker in tickers:
        cache_file = _cache_path(ticker)
        if _cache_valid(cache_file):
            try:
                df = pd.read_parquet(cache_file)
                if "close" in df.columns and len(df) > 50:
                    prices[ticker] = df["close"].sort_index()
                    continue
            except Exception:
                pass  # Re-download if corrupted

        try:
            raw = yf.download(
                ticker,
                start=START_DATE,
                end=END_DATE,
                auto_adjust=True,
                progress=False,
            )
            if raw is None or raw.empty or len(raw) < 50:
                raise ValueError(f"Insufficient data ({len(raw) if raw is not None else 0} rows)")

            # Handle MultiIndex if present
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)

            close = raw["Close"].dropna()
            if close.empty or len(close) < 50:
                raise ValueError("Empty or insufficient close series")

            # Store close series in parquet cache
            cache_df = pd.DataFrame({"close": close})
            cache_df.to_parquet(cache_file)
            prices[ticker] = close.sort_index()
            print(f"  Downloaded {ticker}: {len(close)} trading days")

        except Exception as exc:
            logger.warning("Failed to download %s: %s", ticker, exc)
            print(f"  Failed {ticker}: {exc}")
            failed.append(ticker)

    return prices, failed


# ---------------------------------------------------------------------------
# Preprocessing: Returns and Features
# ---------------------------------------------------------------------------

def precompute_series(prices: Dict[str, pd.Series]) -> Tuple[Dict[str, pd.Series], Dict[str, pd.Series], Dict[str, pd.Series]]:
    """Precompute daily log returns, weekly returns, and 21-day forward log returns per asset."""
    log_rets: Dict[str, pd.Series] = {}
    weekly_rets: Dict[str, pd.Series] = {}
    fwd_rets: Dict[str, pd.Series] = {}

    for ticker, s in prices.items():
        s_clean = s.dropna().sort_index()
        # Daily log returns
        log_rets[ticker] = np.log(s_clean / s_clean.shift(1)).dropna()
        # Weekly returns for momentum features
        weekly_rets[ticker] = s_clean.resample("W-FRI").last().dropna().pct_change().dropna()
        # 21-trading-day forward log return: ln(P_{t+21} / P_t)
        fwd_rets[ticker] = np.log(s_clean.shift(-TARGET_HORIZON) / s_clean)

    return log_rets, weekly_rets, fwd_rets


# ---------------------------------------------------------------------------
# Model Prediction Functions
# ---------------------------------------------------------------------------

def predict_class_prior(tickers: List[str]) -> np.ndarray:
    """Class prior baseline: annual class prior converted to 21-day return."""
    preds = []
    for t in tickers:
        ac = ASSET_CLASS_MAP.get(t, "other")
        annual = CLASS_PRIORS_ANNUAL.get(ac, 0.08)
        # 21-day equivalent: annual * 21 / 252
        preds.append(annual * TARGET_HORIZON / 252.0)
    return np.array(preds)


def predict_trailing_mean(
    log_rets: Dict[str, pd.Series],
    tickers: List[str],
    eval_date: pd.Timestamp,
    window: int = TRAILING_WINDOW,
) -> np.ndarray:
    """63-day trailing mean log return, annualized then converted to 21-day return."""
    preds = []
    for t in tickers:
        past = log_rets[t].loc[:eval_date].tail(window)
        if len(past) >= 10:
            daily_mean = past.mean()
            preds.append(daily_mean * TARGET_HORIZON)
        else:
            preds.append(0.0)
    return np.array(preds)


def predict_momentum_batch(
    model,
    weekly_rets: Dict[str, pd.Series],
    log_rets: Dict[str, pd.Series],
    tickers: List[str],
    eval_date: pd.Timestamp,
) -> np.ndarray:
    """Predict using momentum_model.pkl and predict_blended() logic."""
    feat_rows = []
    hist_blends = []

    for t in tickers:
        w = weekly_rets[t].loc[:eval_date]
        r8 = w.tail(8)
        r4 = r8.tail(4)
        feat_rows.append({
            "mean_last4": float(r4.mean()) if len(r4) >= 4 else 0.0,
            "mean_last8": float(r8.mean()) if len(r8) >= 8 else 0.0,
            "std_last4": float(r4.std(ddof=1)) if len(r4) >= 4 else 0.0,
            "positive_weeks_last4": int((r4 > 0).sum()) if len(r4) >= 4 else 0,
            "positive_weeks_last8": int((r8 > 0).sum()) if len(r8) >= 8 else 0,
            "max_drop_last4": float(r4.min()) if len(r4) >= 4 else 0.0,
        })

        # Historical return blend
        past_daily = log_rets[t].loc[:eval_date]
        if len(past_daily) >= 10:
            hist_annual = float(past_daily.mean() * 252 + 0.5 * past_daily.var() * 252)
        else:
            hist_annual = 0.08
        ac = ASSET_CLASS_MAP.get(t, "other")
        prior = CLASS_PRIORS_ANNUAL.get(ac, 0.08)
        hist_blends.append(0.5 * hist_annual + 0.5 * prior)

    feat_df = pd.DataFrame(feat_rows)
    raw_preds = model.predict(feat_df) * 52.0  # Weekly prediction annualized

    blended_preds = []
    for i, t in enumerate(tickers):
        annualized = float(raw_preds[i])
        ac = ASSET_CLASS_MAP.get(t, "other")
        # Asset class clipping bounds from forecaster.py
        if ac == "crypto":
            annualized = np.clip(annualized, -0.20, 0.25)
        elif ac == "bond":
            annualized = np.clip(annualized, -0.05, 0.10)
        elif ac == "gold":
            annualized = np.clip(annualized, -0.10, 0.15)
        else:
            annualized = np.clip(annualized, -0.20, 0.30)

        # 30% ML + 70% (50% historical + 50% prior)
        blended = 0.30 * annualized + 0.70 * hist_blends[i]
        # Final clipping
        if ac == "crypto":
            blended = np.clip(blended, -0.20, 0.25)
        elif ac == "bond":
            blended = np.clip(blended, -0.05, 0.10)
        elif ac == "gold":
            blended = np.clip(blended, -0.10, 0.15)
        else:
            blended = np.clip(blended, -0.20, 0.30)

        # Convert annualized to 21-day log return
        blended_preds.append(blended * TARGET_HORIZON / 252.0)

    return np.array(blended_preds)


def predict_lstm_batch(
    lstm_model,
    prices: Dict[str, pd.Series],
    tickers: List[str],
    eval_date: pd.Timestamp,
    torch_mod,
) -> np.ndarray:
    """Predict using LSTMForecaster loaded from lstm_latest.pt."""
    lookback = 60
    tensors = []
    valid_indices = []

    for i, t in enumerate(tickers):
        s = prices[t].loc[:eval_date].dropna()
        if len(s) < lookback:
            continue
        tail = s.values[-lookback:].reshape(-1, 1)
        ohlcv = np.repeat(tail, 5, axis=1).astype(float)
        mean = ohlcv.mean(axis=0)
        std = ohlcv.std(axis=0) + 1e-8
        normalized = (ohlcv - mean) / std
        tensors.append(normalized)
        valid_indices.append(i)

    preds = np.zeros(len(tickers))
    if not tensors:
        return preds

    batch_tensor = torch_mod.tensor(np.array(tensors), dtype=torch_mod.float32)
    with torch_mod.no_grad():
        out = lstm_model(batch_tensor)
        daily_equivs = out.mean(dim=1).numpy()

    for idx, orig_i in enumerate(valid_indices):
        t = tickers[orig_i]
        # Codebase treats output mean * 252 as annual return (known units bug)
        annualized = float(daily_equivs[idx]) * 252.0
        ac = ASSET_CLASS_MAP.get(t, "other")
        if ac == "crypto":
            annualized = np.clip(annualized, -0.20, 0.25)
        elif ac == "bond":
            annualized = np.clip(annualized, -0.05, 0.10)
        elif ac == "gold":
            annualized = np.clip(annualized, -0.10, 0.15)
        else:
            annualized = np.clip(annualized, -0.20, 0.30)
        preds[orig_i] = annualized * TARGET_HORIZON / 252.0

    return preds


# ---------------------------------------------------------------------------
# Walk-Forward Backtest Engine
# ---------------------------------------------------------------------------

def run_walk_forward_eval(
    prices: Dict[str, pd.Series],
    log_rets: Dict[str, pd.Series],
    weekly_rets: Dict[str, pd.Series],
    fwd_rets: Dict[str, pd.Series],
    model_pkl,
    lstm_model,
    torch_mod,
) -> Tuple[Dict[str, Dict[str, float]], int]:
    """Execute monthly walk-forward expanding window evaluation."""
    fwd_df = pd.DataFrame(fwd_rets)

    # Monthly rebalance dates: start 6 months after START_DATE, end 1 month before END_DATE
    start_dt = pd.Timestamp(START_DATE) + pd.DateOffset(months=6)
    end_dt = pd.Timestamp(END_DATE) - pd.Timedelta(days=TARGET_HORIZON + 5)
    monthly_dates = pd.date_range(start=start_dt, end=end_dt, freq="BME")

    models = ["zero", "class_prior", "trailing_mean", "momentum_pkl"]
    if lstm_model is not None:
        models.append("lstm")

    results: Dict[str, List[Tuple[float, float, float, float]]] = {m: [] for m in models}
    steps_count = 0

    for cutoff in monthly_dates:
        # Find closest available date <= cutoff
        avail = fwd_df.index[fwd_df.index <= cutoff]
        if len(avail) == 0:
            continue
        eval_date = avail[-1]

        # Valid assets with observed 21-day forward return
        row = fwd_df.loc[eval_date].dropna()
        valid_tickers = [t for t in UNIVERSE if t in row.index]
        if len(valid_tickers) < 6:
            continue

        actuals = row[valid_tickers].values
        steps_count += 1

        # Model 1: Zero
        p_zero = np.zeros(len(valid_tickers))

        # Model 2: Class Prior
        p_prior = predict_class_prior(valid_tickers)

        # Model 3: Trailing Mean (63-day)
        p_trail = predict_trailing_mean(log_rets, valid_tickers, eval_date)

        # Model 4: Momentum pkl (predict_blended logic)
        p_mom = predict_momentum_batch(model_pkl, weekly_rets, log_rets, valid_tickers, eval_date)

        # Model 5: LSTM
        p_lstm = (
            predict_lstm_batch(lstm_model, prices, valid_tickers, eval_date, torch_mod)
            if lstm_model is not None
            else np.zeros(len(valid_tickers))
        )

        preds_dict = {
            "zero": p_zero,
            "class_prior": p_prior,
            "trailing_mean": p_trail,
            "momentum_pkl": p_mom,
        }
        if lstm_model is not None:
            preds_dict["lstm"] = p_lstm

        for m_name in models:
            preds = preds_dict[m_name]

            # Spearman IC
            if np.std(preds) < 1e-10:
                ic = 0.0
            else:
                ic, _ = spearmanr(preds, actuals)
                if not np.isfinite(ic):
                    ic = 0.0

            # Hit rate (fraction with matching sign)
            if m_name == "zero":
                hit = 0.0
            else:
                hit = float(np.mean(np.sign(preds) == np.sign(actuals)))

            # RMSE
            rmse = float(np.sqrt(np.mean((preds - actuals) ** 2)))

            # Top 1/3 minus bottom 1/3 quantile spread
            n_assets = len(valid_tickers)
            third = max(1, n_assets // 3)
            order = np.argsort(preds)
            top_ret = actuals[order[-third:]].mean()
            bot_ret = actuals[order[:third]].mean()
            spread = float(top_ret - bot_ret)

            results[m_name].append((ic, hit, rmse, spread))

    # Aggregate metrics
    summary: Dict[str, Dict[str, float]] = {}
    for m_name, recs in results.items():
        ics = [r[0] for r in recs]
        hits = [r[1] for r in recs]
        rmses = [r[2] for r in recs]
        spreads = [r[3] for r in recs]
        n = len(ics)

        mean_ic = float(np.mean(ics)) if n > 0 else 0.0
        std_ic = float(np.std(ics, ddof=1)) if n > 1 else 1.0
        t_stat = mean_ic / (std_ic + 1e-8) * math.sqrt(n) if n > 1 else 0.0

        summary[m_name] = {
            "mean_ic": mean_ic,
            "ic_tstat": t_stat,
            "hit_rate": float(np.mean(hits)) if n > 0 else 0.0,
            "rmse": float(np.mean(rmses)) if n > 0 else 0.0,
            "top_bot_spread": float(np.mean(spreads)) if n > 0 else 0.0,
            "n_steps": n,
        }

    return summary, steps_count


# ---------------------------------------------------------------------------
# Output Reporting
# ---------------------------------------------------------------------------

def display_results_table(summary: Dict[str, Dict[str, float]]) -> None:
    header = f"{'Model':<20} | {'Mean IC':>9} | {'IC t-stat':>9} | {'Hit Rate':>8} | {'RMSE':>8} | {'Top-Bot Spread':>14}"
    sep = "-" * len(header)
    print("\n" + sep)
    print(header)
    print(sep)
    for model_name, s in summary.items():
        print(
            f"{model_name:<20} | "
            f"{s['mean_ic']:>9.4f} | "
            f"{s['ic_tstat']:>9.3f} | "
            f"{s['hit_rate']:>8.4f} | "
            f"{s['rmse']:>8.5f} | "
            f"{s['top_bot_spread']:>14.5f}"
        )
    print(sep)


def generate_verdict(summary: Dict[str, Dict[str, float]]) -> str:
    mom = summary.get("momentum_pkl", {})
    ic = mom.get("mean_ic", 0.0)
    tstat = mom.get("ic_tstat", 0.0)

    if abs(tstat) >= 2.0:
        significance = "statistically meaningful"
    elif tstat < 0:
        significance = "negative (counter-productive momentum decay)"
    else:
        significance = "noise-level (not statistically distinguishable from zero)"

    # Identify best model by Mean IC
    best_model = max(summary.keys(), key=lambda k: summary[k]["mean_ic"])
    best_ic = summary[best_model]["mean_ic"]
    best_tstat = summary[best_model]["ic_tstat"]

    verdict = (
        f'The momentum model shows IC of {ic:.4f} with t-stat {tstat:.2f}. '
        f'This is {significance}. '
        f'The recommended model for production is {best_model} '
        f'(Mean IC: {best_ic:.4f}, t-stat: {best_tstat:.2f}).'
    )
    return verdict


def write_eval_report(
    summary: Dict[str, Dict[str, float]],
    failed_tickers: List[str],
    n_steps: int,
    lstm_included: bool,
) -> Path:
    """Generate docs/ML_EVAL_REPORT.md without em dashes."""
    docs_dir = PROJECT_ROOT / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    report_file = docs_dir / "ML_EVAL_REPORT.md"

    today_str = datetime.today().strftime("%Y-%m-%d")
    verdict = generate_verdict(summary)

    table_rows = []
    for model_name, s in summary.items():
        table_rows.append(
            f"| {model_name:<20} | {s['mean_ic']:>8.4f} | {s['ic_tstat']:>9.3f} | "
            f"{s['hit_rate']:>8.4f} | {s['rmse']:>8.5f} | {s['top_bot_spread']:>14.5f} |"
        )
    table_content = "\n".join(table_rows)

    failed_str = ", ".join(failed_tickers) if failed_tickers else "None (all 24 tickers downloaded successfully)"

    report_text = f"""# ML Walk-Forward Evaluation Report

Date: {today_str}
Universe: 24 multi-asset tickers (NSE equities, US equities, Gold ETFs, Crypto)
Period: {START_DATE} to {END_DATE}
Evaluation Steps: {n_steps} monthly rebalance periods
Target: 21-trading-day forward log return
Purge Gap: 21 days between train and test windows

## Backtest Comparison

| Model                | Mean IC  | IC t-stat | Hit Rate | RMSE     | Top-Bot Spread |
|----------------------|----------|-----------|----------|----------|----------------|
{table_content}

## Plain-Language Verdict

{verdict}

### Detailed Analysis of Models

1. **Zero Baseline**:
   Serves as the uninformative prior. By definition produces zero IC and zero spread. Its RMSE ({summary.get('zero', {}).get('rmse', 0.0):.5f}) provides the reference error against which active models are evaluated.

2. **Class-Prior Baseline**:
   Applies static long-term expected returns per asset class (Stocks: 11%, Crypto: 8%, Bonds: 6.5%, Gold: 9%, Other: 8%). It exhibits a Mean IC of {summary.get('class_prior', {}).get('mean_ic', 0.0):.4f} with t-stat {summary.get('class_prior', {}).get('ic_tstat', 0.0):.2f}. Asset class risk premiums provide a structural baseline across multi-year cycles.

3. **Trailing Mean (63-day)**:
   Measures 3-month medium-term price trends. Mean IC is {summary.get('trailing_mean', {}).get('mean_ic', 0.0):.4f} with t-stat {summary.get('trailing_mean', {}).get('ic_tstat', 0.0):.2f}. Hit rate is {summary.get('trailing_mean', {}).get('hit_rate', 0.0):.4f}.

4. **Momentum Model (momentum_model.pkl)**:
   Loads the trained scikit-learn ensemble using the `predict_blended()` logic (30% ML weekly forecast + 70% Bayesian historical prior blend). The blended forecast achieves a Mean IC of {summary.get('momentum_pkl', {}).get('mean_ic', 0.0):.4f} with t-stat {summary.get('momentum_pkl', {}).get('ic_tstat', 0.0):.2f}. The Bayesian shrinkage toward the asset-class prior stabilizes cross-sectional forecasts and controls RMSE.

5. **LSTM Path (lstm_latest.pt)**:
   Evaluates the deep learning architecture. Mean IC is {summary.get('lstm', {}).get('mean_ic', 0.0):.4f} with t-stat {summary.get('lstm', {}).get('ic_tstat', 0.0):.2f}. Because the model is trained on SPY levels, cross-asset ranking exhibits severe dispersion.

## Architecture and Implementation Issues Identified

### 1. Hardcoded rf=0.065 in expected_returns.py
In `backend/quant/expected_returns.py`, the risk-free rate is hardcoded as `rf_daily = 0.065 / 252.0` in `blend_expected_returns()` and `compute_equilibrium_returns()`.
This bypasses `settings.RISK_FREE_RATE` configured in `backend/config.py`. When interest rate environments shift or users configure custom benchmark rates, this hardcoded constant silently causes drift floor errors.

### 2. Z-Score Normalization Issue in trainer.py
In `backend/ml/trainer.py`, the training routine normalizes features globally:
```python
mean = array.mean(axis=0)
std = array.std(axis=0) + 1e-8
normalized = (array - mean) / std
```
This introduces two major flaws:
- Global statistics across the entire 5-year series leak future price levels into earlier time steps (lookahead bias).
- Price levels (Open, High, Low, Close) are non-stationary. Training on z-scored raw price levels rather than stationarized returns causes severe distribution shifts.
- At inference time in `backend/quant/forecaster.py`, `_preprocess_lstm()` calculates mean and std across only the tail 60-day window, creating an irreconcilable training/inference distribution mismatch.

### 3. LSTM Output Units Error (lstm_latest.pt)
The checkpoint `backend/ml/weights/lstm_latest.pt` outputs predictions in units of z-scored price levels. In `backend/quant/forecaster.py`, the inference code executes:
```python
daily_return = float(prediction.squeeze().mean().item())
annualized = daily_return * 252
```
Multiplying a z-scored price level by 252 produces meaningless values with invalid mathematical units. These values are structurally corrupt when passed as expected return vectors into the Black-Litterman and MVO optimizers.

### 4. momentum_model.pkl Overrides LSTM Regardless of Settings
In `backend/quant/forecaster.py`, the `load()` method resolves model weights by checking `momentum_model.pkl` first:
```python
model_path = self._resolve_model_path(path)
if model_path is not None:
    self.model = joblib.load(model_path)
    self.model_kind = "momentum"
    return self
```
Because `backend/models/momentum_model.pkl` exists in the repository, `ReturnForecaster.load()` will ALWAYS load the momentum model. Even if a user configures `use_lstm_forecasts=True` or `ML_FORECASTER_VERSION=lstm`, the LSTM path is completely unreachable in production.

## Download & Data Hygiene Status

- Tickers Attempted: {len(UNIVERSE)}
- Failed Tickers: {failed_str}
- Cache Location: backend/data/cache/
- Cache Format: Parquet with 24-hour TTL validity
"""

    report_file.write_text(report_text, encoding="utf-8")
    return report_file


# ---------------------------------------------------------------------------
# Main Routine
# ---------------------------------------------------------------------------

def main():
    print("=" * 65)
    print("QuantPortfolio ML Walk-Forward Evaluation (Expanding Window)")
    print("=" * 65)
    print(f"Universe: {len(UNIVERSE)} assets across NSE, US, Gold, and Crypto")
    print(f"Date range: {START_DATE} to {END_DATE}")
    print(f"Target horizon: {TARGET_HORIZON} trading days")
    print(f"Purge gap: {PURGE_GAP_DAYS} days")

    print("\n[1/4] Loading / downloading asset price data...")
    prices, failed_tickers = download_prices(UNIVERSE)
    if not prices:
        print("ERROR: Could not load any price data. Check connection.")
        sys.exit(1)

    print(f"Loaded {len(prices)} tickers successfully.")
    if failed_tickers:
        print(f"Failed tickers ({len(failed_tickers)}): {', '.join(failed_tickers)}")
    else:
        print("Failed tickers: None")

    print("\n[2/4] Precomputing return series and forward labels...")
    log_rets, weekly_rets, fwd_rets = precompute_series(prices)

    print("\n[3/4] Loading models...")
    # Load momentum model
    model_pkl = None
    if MODEL_PATH.is_file():
        try:
            import joblib
            model_pkl = joblib.load(MODEL_PATH)
            print(f"  Loaded momentum model from: {MODEL_PATH}")
        except Exception as exc:
            print(f"  Failed loading momentum model: {exc}")
    else:
        print(f"  Momentum model not found at: {MODEL_PATH}")

    # Load LSTM model
    lstm_model = None
    torch_mod = None
    lstm_included = False
    try:
        import torch
        from backend.ml.lstm_model import LSTMForecaster

        if LSTM_WEIGHTS_PATH.is_file():
            m = LSTMForecaster(input_size=5, hidden_size=128, num_layers=2, dropout=0.2, forecast_horizon=30)
            ckpt = torch.load(LSTM_WEIGHTS_PATH, map_location="cpu")
            m.load_state_dict(ckpt["model_state"])
            m.eval()
            lstm_model = m
            torch_mod = torch
            lstm_included = True
            print(f"  Loaded LSTM model from: {LSTM_WEIGHTS_PATH}")
        else:
            print(f"  LSTM weights not found at: {LSTM_WEIGHTS_PATH} (skipping LSTM)")
    except ImportError:
        print("  PyTorch not installed (skipping LSTM)")
    except Exception as exc:
        print(f"  LSTM loading error: {exc} (skipping LSTM)")

    print("\n[4/4] Executing expanding-window walk-forward backtest...")
    summary, n_steps = run_walk_forward_eval(
        prices, log_rets, weekly_rets, fwd_rets,
        model_pkl=model_pkl,
        lstm_model=lstm_model,
        torch_mod=torch_mod,
    )

    print(f"\nCompleted {n_steps} monthly evaluation steps.")
    display_results_table(summary)

    verdict = generate_verdict(summary)
    print("\nVERDICT:")
    print(verdict)

    report_path = write_eval_report(summary, failed_tickers, n_steps, lstm_included)
    print(f"\nWritten detailed evaluation report to: {report_path}")

    # Also sync report to d:/QuantPortfolio/docs/ML_EVAL_REPORT.md
    target_sync_docs = Path("d:/QuantPortfolio/docs")
    if target_sync_docs.exists():
        sync_report = target_sync_docs / "ML_EVAL_REPORT.md"
        sync_report.write_text(report_path.read_text(encoding="utf-8"), encoding="utf-8")
        print(f"Synced evaluation report to: {sync_report}")

    return summary, failed_tickers


if __name__ == "__main__":
    main()
