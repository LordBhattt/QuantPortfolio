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
**Inverse Volatility** using data through 2023-04-28; the final 40% was held
out. The held-out result did not beat Equal Weight.

| Strategy | Profit (INR) | Sharpe | Max drawdown |
|---|---:|---:|---:|
| QP Smart / Inverse Volatility | +38,276.24 | +0.0012 | -16.21% |
| Equal Weight | +47,141.66 | +0.1452 | -16.51% |
| No-trade 10%, quarterly (not selected) | +69,295.07 | +0.4114 | -14.91% |
| SPY reference | +90,119.12 | n/a | n/a |

The volatility model was rejected before selection (held-out MAE 0.1052 versus
0.0502 for trailing volatility). The block-bootstrap 95% interval for QP Smart
versus Equal Weight was [-0.0027, 0.0009], not statistically significant.

#### Final live 3-year talking points (run 2026-11-13)

The seeded demo portfolio was run with monthly rebalancing, risk tolerance 0.5, 10 bps
transaction costs, and ML OFF. QP Smart selected **Hierarchical Risk Parity**
through 2025-09-12 using train-period data only. These are live-data results, so
they will change as the market window advances:

| Strategy | Profit (INR) | Sharpe | Max drawdown |
|---|---:|---:|---:|
| QP Smart / Hierarchical Risk Parity | +26,148.00 | +0.23 | -12.09% |
| Equal Weight | +26,864.30 | +0.18 | -17.23% |
| Optimized | +20,313.40 | -0.02 | -15.04% |
| Buy and Hold | +12,907.20 | -0.25 | -15.84% |
| SPY | +66,598.48 | +0.78 | -18.76% |

The unflattering result is important: QP Smart slightly underperformed Equal
Weight by INR 716.30, while reducing maximum drawdown by 5.14 percentage points.
SPY is a reference benchmark only and is not constrained across the portfolio's
five asset classes.

Backtest results are historical and are not a guarantee of future returns.

#### If asked

- **Why does SPY have higher returns?** SPY is an unconstrained single-market
  reference benchmark. QP Smart must diversify across five asset classes and
  obey the portfolio's class bounds.
- **Why is ML off?** The held-out volatility model loses to trailing volatility,
  and the return models fail their IC and t-stat gates. The UI therefore shows
  "ML not used" rather than using an unvalidated forecast.
- **What is a backtest?** It replays a strategy against historical prices,
  including the configured transaction costs, to show how it would have behaved.
- **What does walk-forward mean?** Each rebalance uses only prices available
  before that rebalance date. Hyperparameters are selected on earlier data and
  then frozen for the held-out period.

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

- All displayed portfolio numbers come from live API calls; unused development fixtures are not part of the application bundle.
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
- Registration, login, and in-app alerts are supported. No SMTP email delivery path is
  configured in this build; configure an SMTP provider before adding email delivery.
