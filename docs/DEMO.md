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
   - **Metrics table**: 6 strategies (Optimized, Equal Weight, Buy and Hold, Min Variance,
     SPY, NIFTY). The best value in each column is highlighted in indigo.
   - **Equity curves**: multi-line Recharts chart, one line per strategy from INR 100,000.
   - **Drawdown chart**: underwater area showing peak-to-trough loss for each strategy.
   - **Weights over time**: stacked area chart showing the Optimized strategy's allocations
     at each rebalance date.
5. Toggle ML Forecast ON to see the effect (gate not passed so difference is minimal --
   that is the honest result; the UI badge on the Optimize page will say "ML not used").

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
2. Run an optimization (risk 0.5, default constraints, ML Forecast toggle ON).
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
