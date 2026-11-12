# ML Walk-Forward Evaluation Report

Date: 2026-11-13
Universe: 24 multi-asset tickers (NSE equities, US equities, Gold ETFs, Crypto)
Period: 2018-01-01 to 2026-11-13
Evaluation Steps: 98 monthly rebalance periods
Target: 21-trading-day forward log return
Purge Gap: 21 days between train and test windows

## Backtest Comparison

| Model                | Mean IC  | IC t-stat | Hit Rate | RMSE     | Top-Bot Spread |
|----------------------|----------|-----------|----------|----------|----------------|
| zero                 |   0.0000 |     0.000 |   0.0000 |  0.08939 |        0.00818 |
| class_prior          |   0.0331 |     1.121 |   0.5641 |  0.08860 |        0.00586 |
| trailing_mean        |  -0.0322 |    -0.984 |   0.5140 |  0.10047 |       -0.00137 |
| momentum_pkl         |   0.0177 |     0.634 |   0.5636 |  0.08882 |       -0.00095 |
| lstm                 |  -0.0232 |    -0.839 |   0.5206 |  0.09067 |       -0.00094 |

## Plain-Language Verdict

The momentum model shows IC of 0.0177 with t-stat 0.63. This is noise-level (not statistically distinguishable from zero). The recommended model for production is class_prior (Mean IC: 0.0331, t-stat: 1.12).

### Detailed Analysis of Models

1. **Zero Baseline**:
   Serves as the uninformative prior. By definition produces zero IC and zero spread. Its RMSE (0.08939) provides the reference error against which active models are evaluated.

2. **Class-Prior Baseline**:
   Applies static long-term expected returns per asset class (Stocks: 11%, Crypto: 8%, Bonds: 6.5%, Gold: 9%, Other: 8%). It exhibits a Mean IC of 0.0331 with t-stat 1.12. Asset class risk premiums provide a structural baseline across multi-year cycles.

3. **Trailing Mean (63-day)**:
   Measures 3-month medium-term price trends. Mean IC is -0.0322 with t-stat -0.98. Hit rate is 0.5140.

4. **Momentum Model (momentum_model.pkl)**:
   Loads the trained scikit-learn ensemble using the `predict_blended()` logic (30% ML weekly forecast + 70% Bayesian historical prior blend). The blended forecast achieves a Mean IC of 0.0177 with t-stat 0.63. The Bayesian shrinkage toward the asset-class prior stabilizes cross-sectional forecasts and controls RMSE.

5. **LSTM Path (lstm_latest.pt)**:
   Evaluates the deep learning architecture. Mean IC is -0.0232 with t-stat -0.84. Because the model is trained on SPY levels, cross-asset ranking exhibits severe dispersion.

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

- Tickers Attempted: 24
- Failed Tickers: None (all 24 tickers downloaded successfully)
- Cache Location: backend/data/cache/
- Cache Format: Parquet with 24-hour TTL validity
