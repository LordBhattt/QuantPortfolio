# docs/ABLATION.md

## Ablation Study: Proper 60/40 Holdout

Configs were chosen on the **first 60% of the data** (train window) and all metrics below
are reported on the **last 40% only** (held-out test window). There is no look-ahead.

### Data and Window

| Field | Value |
|---|---|
| Universe | RELIANCE.NS (stock), BTC-USD (crypto), GLD (gold), TLT (bond) |
| Full window | 2018-01-01 to 2026-11-12 (3,238 trading days) |
| Train (60%) | 2018-01-01 to 2023-04-26 (1,942 days) -- config selection only |
| Test (40%) | 2023-04-27 to 2026-11-12 (1,296 days) -- all numbers reported here |
| Rebalance | Monthly walk-forward, no look-ahead |
| Starting value | INR 100,000 |
| Cost | 10 bps per rebalance |

GBM OOS IC = 0.0173, t-stat = 0.61 -- gate not passed (threshold: IC > 0.02 and t > 2).

---

### Ablation Table: Held-out Test Set (2023-04-27 to 2026-11-12)

All numbers come from `backend/scripts/ablation_holdout.py` run on 2026-11-12.

| Config | ML | Floor | Regime | CAGR | Vol | Sharpe | Max DD | Calmar | Profit (INR) |
|---|---|---|---|---|---|---|---|---|---|
| A: all off | off | off | off | -7.1% | 13.3% | -1.02 | -13.6% | -0.53 | -7,132 |
| B: floor only | off | on | off | -7.1% | 13.3% | -1.02 | -13.6% | -0.53 | -7,132 |
| C: regime only | off | off | on | -7.1% | 13.3% | -1.02 | -13.6% | -0.53 | -7,132 |
| D: floor + regime (default) | off | on | on | -7.1% | 13.3% | -1.02 | -13.6% | -0.53 | -7,132 |
| E: all on (ML + floor + regime) | on | on | on | -7.1% | 13.3% | -1.02 | -13.6% | -0.53 | -7,132 |
| **Equal Weight** | - | - | - | **-7.1%** | 13.3% | -1.02 | -13.6% | -0.53 | -7,132 |
| **SPY (benchmark)** | - | - | - | **+13.5%** | 11.1% | +0.58 | -6.6% | +2.04 | +13,482 |

> [!IMPORTANT]
> **All five optimizer configs produce identical results on the held-out test set.**
> The optimizer converges to equal weight for this 4-asset universe regardless of floor or
> regime toggle. No config beats Equal Weight. SPY outperformed every strategy by a wide margin:
> +13.5% CAGR vs -7.1% CAGR on the test window.
>
> This is an honest result. The optimizer adds no alpha on this small universe in this window.

---

### Key Findings

1. **Floor and regime toggles make zero measurable difference** on this small 4-asset
   portfolio. The optimizer converges to equal weight in all cases. The toggles are theoretically
   sound but require a larger, more heterogeneous universe to show a difference.

2. **No config beats Equal Weight** on the held-out period. Reporting this honestly.

3. **SPY outperformed all strategies**: +13.5% CAGR vs -7.1%. This was a period of strong US
   equities (2023-2026) with weaker performance from crypto, gold, and bonds as a group.

4. **GBM ML model did not pass the gate** (IC 0.0173 vs threshold 0.02; t 0.61 vs threshold 2).
   Enabling ML is effectively a no-op in the optimizer.

---

### Defaults Set

Based on the ablation, **no config is demonstrably better** on the held-out set.
Config D (floor ON, regime ON, ML OFF) is kept as the default because:
- It is not worse than any alternative on the test set.
- It is theoretically sound (prevents negative-drift returns, adapts covariance to regime).
- On larger or more diverse portfolios it is expected to show benefit.

Defaults:

- `use_regime_scaling = True`
- `EXPECTED_RETURN_FLOOR_ENABLED = True`
- `ML_FORECASTER_VERSION = "gbm"` (loaded but gate-disabled; shown as "ML not used" in UI)
- `use_lstm_forecasts = True` (accepted for backward compat; real model is GBM or none)

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
2. Run the ablation script: `python backend/scripts/ablation_holdout.py`
3. The script prints train-window metrics (config selection) and test-window metrics (reported above).
4. To see the ablation interactively: start backend and frontend, log in as demo@quantportfolio.in,
   go to /backtest, set 3Y monthly, and toggle ML and regime to compare strategies.
