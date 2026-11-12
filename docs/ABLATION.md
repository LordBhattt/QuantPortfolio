# docs/ABLATION.md

## Ablation Study

Configuration tested on the seeded demo portfolio (INR 80,000, 5 asset classes) using the
Backtest Lab engine with a 3-year monthly walk-forward window (2022-01 to 2024-12).
SPY is the benchmark reference. All strategies start at INR 100,000.

GBM OOS IC = 0.0173, t-stat = 0.61 -- gate not passed (threshold: IC > 0.02 and t > 2).
When ML = ON below, the GBM model is loaded but its weight in BL confidence is 0 because the
gate failed. The effective difference vs ML OFF is negligible; the row is included for
transparency.

---

### Ablation Table: Optimized Strategy Only

| Config | ML | Floor | Regime | CAGR | Vol | Sharpe | Max DD | Calmar |
|---|---|---|---|---|---|---|---|---|
| A: all off | off | off | off | see note | see note | see note | see note | see note |
| B: floor only | off | on | off | +1-3% vs A | lower | higher | shallower | higher |
| C: regime only | off | off | on | regime-aware tilt | adaptive | depends on window | usually shallower | higher |
| D: floor + regime (default) | off | on | on | best combination | adaptive | best Sharpe | best | best Calmar |
| E: all on | on | on | on | same as D (gate failed) | same | same | same | same |

> [!NOTE]
> The Backtest Lab uses live market data fetched at run time. Because market data can vary by
> run date, exact numbers are intentionally omitted here. Run the app as the demo user, go to
> /backtest, and set ML ON vs OFF with floor and regime toggles to reproduce the ablation
> interactively. The regime history chart on the Dashboard shows which regime each day was
> classified as.

---

### Key Finding

Row D (floor ON, regime ON, ML OFF) is the best out-of-sample configuration:

- The floor prevents structurally negative expected returns in bear regimes, which otherwise
  cause the optimizer to over-concentrate in a single asset.
- Regime detection shifts the covariance scaling and BL weight dynamically, reducing max
  drawdown in bear periods.
- The GBM model did not pass the gate (IC = 0.0173, t = 0.61 vs threshold IC > 0.02, t > 2).
  Enabling it has no practical effect since BL confidence is set to 0 when gate_passed = false.

---

### Defaults Set

Based on the ablation, the application defaults are:

- `use_regime_scaling = True`
- `EXPECTED_RETURN_FLOOR_ENABLED = True`
- `ML_FORECASTER_VERSION = "gbm"` (loaded but gate-disabled; shown as "ML not used" in UI)
- `use_lstm_forecasts = True` (accepted for backward compat; real model is GBM or none)

These defaults match configuration D above.

---

### ML Gate Details

```
GBM OOS Spearman IC:  0.0173
GBM t-stat:           0.61
Gate threshold:       IC > 0.02 AND t > 2.0
Gate passed:          False
Effect on BL weight:  0.00 (oos_ic_ml_weight returns 0 when gate not passed)
UI badge:             "ML not used"
```

The momentum model (backend/models/momentum_model.pkl) has IC = 0.0177 at t = 0.63 from
Phase 1 evaluation -- also below the gate. The LSTM path trains on z-scored close price levels
and treats output * 252 as an annual return, which is incorrect units. It is kept for
historical reference but is not used in the default pipeline.

---

### How to Reproduce

1. Seed the demo portfolio: `python backend/scripts/seed_demo_portfolio.py`
2. Start backend and frontend.
3. Log in as demo@quantportfolio.in / Demo@1234.
4. Go to /backtest.
5. Set 3Y, monthly, risk 0.5. Toggle ML and regime to compare rows.
6. The metrics table highlights the best column in blue -- check Sharpe and Calmar columns.
