# docs/DEMO.md

## 5-Minute Invigilator Demo

### Setup (do this before the demo)

```bash
# 1. Seed the demo portfolio (one-time, needs internet for real prices)
cd d:\QuantPortfolio
python backend/scripts/seed_demo_portfolio.py

# 2. Start backend
uvicorn backend.main:app --reload

# 3. Start frontend (new terminal)
cd frontend
npm run dev
```

Open: http://localhost:5173

---

### Step 1 (45 seconds): Login and Dashboard

1. Click "Sign in", enter:
   - Email: demo@quantportfolio.in
   - Password: Demo@1234
2. The Dashboard loads immediately.
3. Point out:
   - **Hero band**: total portfolio value in INR (live price, not hardcoded).
   - **P&L cards**: each holding's gain/loss = live price minus the avg_buy_price that was
     set from the real historical close 12 months ago when the portfolio was seeded.
   - **Regime chart** (bottom of Dashboard): SPY close price with coloured area overlays
     showing bull (green), sideways (yellow), and bear (red) regimes detected by the HMM
     model. The chart uses live data from the API -- every label is computed from the
     fitted HMM at render time.
   - **Model Track Record card**: shows the GBM OOS IC (0.0173, gate not passed). Click
     it to go to the Backtest Lab.

---

### Step 2 (90 seconds): Backtest Lab (/backtest)

1. Click "Backtest" in the nav bar or the Model Track Record card.
2. Set controls: 3 years, monthly rebalance, risk 0.5, 10 bps cost.
3. Click Run Backtest. Wait up to 30 seconds for the first run (cached for 1 hour after).
4. Point out:
   - **Headline card**: "Optimized vs Equal Weight over 3Y: +INR X" (green) or "-INR X"
     (red). Honest result -- if the optimizer underperformed equal weight, it shows red.
   - **Metrics table**: 7 strategies (Optimized, QP Smart, Equal Weight, Buy and Hold,
     Min Variance, SPY, NIFTY). The best value in each column is highlighted in indigo.
   - **Equity curves**: multi-line Recharts chart, one line per strategy from INR 100,000.
   - **Drawdown chart**: underwater area showing peak-to-trough loss for each strategy.
   - **Weights over time**: stacked area chart showing the QP Smart strategy's allocations
     at each rebalance date.
5. ML Forecast and Regime Scaling default to OFF because the five-year evaluation
   did not justify either option. They can be enabled explicitly for comparison.

#### Five-year held-out talking points (run 2026-11-13)

The strict 5-year walk-forward evaluation is documented in
[IMPROVEMENT_REPORT.md](IMPROVEMENT_REPORT.md). QP Smart selected
**Shrinkage lambda=0 (equal weight)** using data through 2023-04-28; the final
40% was held out. It did not beat Equal Weight because it is intentionally the
same weights. No-trade 10% quarterly had the strongest held-out result, but it
was not promoted because choosing it would look at the holdout.

| Strategy | Profit (INR) | Sharpe | Max drawdown |
|---|---:|---:|---:|
| QP Smart / Equal Weight | +47,141.66 | +0.1452 | -16.51% |
| No-trade 10%, quarterly (not selected) | +64,584.94 | +0.3510 | -16.71% |
| SPY reference | +90,119.12 | — | — |

The volatility model was rejected before selection (held-out MAE 0.4796 versus
0.0503 for trailing volatility).

#### Previous live 3-year talking points (run 2026-11-13)

The seeded demo portfolio was run with monthly rebalancing, risk tolerance 0.5, 10 bps
transaction costs, and ML OFF. These are live-data results, so they will change as the
market window advances:

| Strategy | Profit (INR) | Sharpe | Max drawdown |
|---|---:|---:|---:|
| Optimized | +16,728.58 | -0.09 | -23.41% |
| Equal Weight | +29,590.99 | +0.22 | -19.89% |
| Buy and Hold | +9,962.58 | -0.25 | -21.70% |
| SPY | +66,598.47 | +0.78 | -18.76% |

The unflattering result is important: Optimized underperformed Equal Weight by INR 12,862.41
and SPY by INR 49,869.89 over this window.

---

### Step 3 (60 seconds): Risk + Stress Test (/risk)

1. Click "Risk" in the nav bar.
2. The existing VaR, CVaR, Monte Carlo, and correlation matrix load from live data.
3. Scroll to the Stress Test section.
4. Three historical scenario cards show:
   - Global Financial Crisis (Sep 2008 to Mar 2009)
   - COVID Crash (Feb 2020 to Mar 2020)
   - 2022 Rate Hike Cycle (Jan 2022 to Oct 2022)
5. Each card shows the portfolio INR impact and a bar chart of per-holding contributions.
   Holdings with no data in the scenario window use an asset-class proxy (e.g., BTC-USD
   for crypto) and are labelled "proxy" in the chart.
6. Use the custom shock sliders:
   - Drag Equities to -20%, Crypto to -40%, Gold to +10%.
   - The impact updates live (debounced 400 ms).

---

### Step 4 (60 seconds): Optimize + Explainability (/optimize)

1. Click "Optimize" in the nav bar.
2. Run an optimization (risk 0.5, default constraints, ML Forecast and Regime Scaling
   toggles OFF).
3. Point out:
   - **Why This Allocation** grouped bar chart: for each asset, shows equilibrium,
     historical, ML, and momentum return components in side-by-side bars. This answers
     "why did the optimizer allocate X% to this asset?"
   - **Regime probability bar**: bull / sideways / bear probabilities from the HMM.
   - **ML badge**: shows "ML not used" because the GBM OOS IC (0.0173) did not pass the
     gate (IC > 0.02, t > 2). This is an honest result -- the model is loaded, the gate
     failed, so the BL confidence for ML views is 0.
   - **Rebalance trades table**: shows what to buy/sell to reach the target allocation.

---

### Step 5 (30 seconds): Summary for the invigilator

- All numbers come from live API calls: no hardcoded demo values anywhere.
- Bad results are shown honestly: GBM IC = 0.0173 did not pass the gate; displayed as
  "ML not used".
- P&L is real: buy prices were fetched from yfinance 12 months ago at seed time.
- The backtest has no lookahead: at each rebalance date only returns up to that date are
  used. Changing future prices does not change earlier rebalance weights (tested in
  backend/tests/test_phase6.py::TestNoLookahead).

---

### Credentials

| Field | Value |
|---|---|
| Email | demo@quantportfolio.in |
| Password | Demo@1234 |
| Portfolio | Demo Portfolio (INR 80,000, 5 asset classes) |

---

### Known Limitations

- Backtest first run can take up to 30 seconds for 3 years, 10 assets. Subsequent runs
  within 1 hour use Redis cache.
- The GBM model needs ~40 tickers and 6 years of data to train well. With 24 tickers and
  short history (2018 to now), IC = 0.0173 is consistent with published research showing
  that short-term equity return prediction is hard.
- The LSTM model (backend/ml/weights/lstm_latest.pt) exists but its training methodology
  is flawed: it trains on z-scored price levels (not returns) and treats output * 252 as
  an annual return (wrong units). It is not used in the production pipeline.
- Regime detection (3-state HMM) uses SPY as the market proxy. Indian-only portfolios
  may see regime mislabelling in periods where US and Indian markets diverged.
