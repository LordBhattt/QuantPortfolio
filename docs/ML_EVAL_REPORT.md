# ML Evaluation Report

## Gate

Production ML is enabled only when mean out-of-sample IC is greater than
0.02, IC t-stat is greater than 2, and the model beats its portfolio baseline
after costs. All reported models remain disabled.

| Model | OOS mean IC | IC t-stat | Verdict |
|---|---:|---:|---|
| GBM return forecaster | 0.0173 | 0.61 | Disabled |
| Momentum model | 0.0177 | 0.63 | Disabled |
| Legacy LSTM evaluation | -0.0232 | -0.84 | Invalid legacy pipeline |
| Corrected LSTM trainer | Not yet evaluated cross-sectionally | n/a | Disabled |
| Volatility GBM | n/a | n/a | Disabled, MAE 0.1052 vs 0.0505 trailing baseline |

### Held-out volatility comparison

The volatility model was trained through 2023-04-28 and evaluated on the
remaining data in 21-trading-day forecast blocks. QLIKE is the standard
volatility loss `forecast / actual - log(forecast / actual) - 1`; lower is
better. Correlation is between predicted and realized forward volatility;
higher is better.

| Forecast | MAE | QLIKE | Correlation |
|---|---:|---:|---:|
| GBM volatility | 0.1052 | 0.4150 | 0.2059 |
| Trailing 63-day volatility | 0.0505 | 0.0749 | 0.7221 |
| HAR-style baseline | 0.1196 | 0.4494 | 0.1574 |

The GBM loses to the trailing-volatility baseline on all three measures, so it
remains disabled. Features use only the trailing 5, 21, and 63-day realized
volatility before each forecast date, and targets are the next 21-day realized
volatility.

The corrected LSTM now trains on daily log OHLCV changes, predicts forward
close log returns, and stores train-only feature statistics in its checkpoint.
The old checkpoint evaluation was not reused because it trained on z-scored
price levels and produced values in incompatible units.

## Data and leakage controls

- Return models use purged walk-forward evaluation with a 21-day horizon and
  embargo.
- Volatility features use only observations before each forecast date.
- Scalers and model parameters are fitted on the training portion only.
- The final 40 percent of the QP Smart period is not used for selection.

## Production behavior

When the GBM metadata fails the gate, the forecaster reports `model_kind=none`
instead of silently falling through to an unvalidated momentum model. The UI
therefore shows `ML not used`. The corrected LSTM is available for a future
cross-sectional evaluation, but it is not enabled by default.
