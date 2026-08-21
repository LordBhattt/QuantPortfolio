# QuantPortfolio

QuantPortfolio is a full-stack portfolio analysis app for tracking holdings, exploring risk, and generating allocation suggestions with a quant-heavy backend. It combines portfolio CRUD, live market data, optimization, risk analytics, Monte Carlo simulation, and factor analysis behind a FastAPI API, then presents the results in a React dashboard.

In plain language: you tell the app what you own, it fetches market history, converts everything into one comparable return series, and then helps answer questions   like:

- What is my portfolio worth today?
- How much risk am I taking?
- Which holdings are driving returns or risk?
- What would a more "optimal" allocation look like?
- How bad could things get in rough scenarios?

## What The App Does

### Product features

- User registration, login, and JWT-based authenticated sessions
- Portfolio creation and selection
- Holding management across stocks, crypto, gold, ETFs/mutual funds, and bonds
- Asset search against a seeded asset universe
- Portfolio dashboard with total value, PnL, allocation, and benchmarked performance
- Optimization page with:
  - Black-Litterman expected return blending
  - constrained mean-variance optimization
  - efficient frontier generation
  - optional user views
  - optional momentum-model-based forecasts
  - optional regime-aware covariance scaling
- Backtest page with:
  - walk-forward, monthly-rebalanced comparison of equal-weight, static MVO, MVO+Ledoit-Wolf, the full BL+LW+HMM production pipeline, and an adaptive regime-conditioned strategy bandit
  - per-strategy CAGR, Sharpe, Sortino, Calmar, max drawdown, and turnover
  - regime-conditional performance breakdown and a block-bootstrap significance test vs. a baseline strategy
- Risk page with:
  - VaR and CVaR
  - max drawdown
  - Sharpe, Sortino, Calmar, and beta
  - asset correlation matrix
  - Monte Carlo simulation fan chart
- Analytics page with:
  - Fama-French 5-factor exposure
  - return attribution
  - risk attribution
  - per-holding PnL and sparkline snapshots

### Supported asset classes

- Stocks
- Crypto
- Gold
- Mutual funds / ETFs
- Bonds

### Supported market data sources

- Yahoo Finance for equities, ETFs, bonds, gold proxies, and FX
- CoinGecko for crypto
- MF API-based mutual fund NAV ingestion path
- Ken French data library for Fama-French daily factors

## Tech Stack

| Layer | Stack |
| --- | --- |
| Frontend | React 18, Vite 5, React Router 6, Tailwind CSS, shadcn/ui, Radix UI, Recharts, Zustand, Axios |
| Frontend testing | Vitest, jsdom |
| Backend API | FastAPI, Pydantic v2, Uvicorn |
| Database | PostgreSQL with SQLAlchemy async engine and Alembic migrations |
| Cache | Redis, with automatic in-memory fallback when Redis is unavailable |
| Quant / math | NumPy, Pandas, SciPy, scikit-learn, CVXPY, hmmlearn, statsmodels |
| ML | scikit-learn momentum forecaster (offline-trained, loaded read-only) |
| Auth | python-jose, Passlib bcrypt |
| Scheduling | APScheduler |
| Reliability | httpx, tenacity retries |

## Architecture At A Glance

```text
frontend (React/Vite)
  -> axios API client
  -> FastAPI routers
  -> service layer
  -> portfolio snapshot + market data fetcher + cache
  -> quant / ML modules
  -> response DTOs
  -> charts and dashboards
```

### Backend structure

```text
backend/
  main.py                 App startup, lifespan, router mounting, exception handling
  config.py               Environment-driven settings
  database.py             Async SQLAlchemy engine/session setup
  cache/redis_cache.py    Redis cache with memory fallback
  routers/                HTTP endpoints
  services/               Business logic
  quant/                  Optimization, risk, factors, regimes, forecasts, backtesting, data fetching
  models/                 SQLAlchemy table definitions and the momentum forecaster's momentum_model.pkl
  schemas/                Pydantic request/response schemas
  scripts/                One-off maintenance scripts (e.g. build_backtest_dataset.py)
  tasks/scheduler.py      Periodic cache refresh and model-maintenance jobs
  tests/                  Backend tests
```

### Frontend structure

```text
frontend/
  src/pages/              Route-level pages
  src/components/         Layout, charts, domain UI, shadcn UI components
  src/api/                Axios wrappers for backend endpoints
  src/hooks/              Data-fetching and UI state hooks
  src/store/              Zustand auth / portfolio state
  src/lib/                Mapping helpers for chart/UI data shaping
  src/test/               Frontend test setup
```

## How The App Works

### User workflow

1. A user registers or signs in.
2. On first use, the onboarding modal creates the first portfolio and seeds default allocation constraints from a selected risk profile.
3. The user adds holdings with ticker, quantity, average buy price, and buy currency.
4. The backend looks up asset metadata to learn the asset class, market, currency, and data source.
5. For analytics, risk, and optimization calls, the backend fetches historical prices for each holding.
6. Prices are converted into a common currency basis when needed and turned into aligned return series.
7. Different quant modules then reuse that same aligned return matrix:
   - optimization builds expected returns and optimal weights
   - risk computes downside and dispersion metrics
   - Monte Carlo simulates future paths
   - analytics decomposes return and factor exposure
8. The frontend maps API responses into charts, tables, pills, and summary cards.

### Backend startup workflow

When the FastAPI app starts, `backend/main.py` does more than just boot the server:

1. Creates database tables from metadata if they do not exist.
2. Seeds a default starter asset list into the `assets` table.
3. Connects to Redis. If Redis is unavailable, caching falls back to an in-memory store.
4. Creates the shared `DataFetcher`.
5. Tries to fit the market regime detector using roughly 3 years of `SPY` history.
6. Tries to load the momentum forecaster from `backend/models/momentum_model.pkl`.
7. Registers those model singletons for the optimization service.
8. Starts scheduled jobs for cache refreshes and model-maintenance reminders.

## Quant Models In Easy Language

This section is the "what do these algorithms actually mean?" version.

### 1. Return alignment and FX normalization

Before any model runs, the app converts each asset's price history into returns and normalizes currencies when needed.

Plain English:

- If one holding is in INR and another is in USD, the backend first makes them comparable.
- Then it looks at day-to-day moves instead of raw prices.
- Finally it lines up dates so each row compares the same trading day across assets.

Why this matters:

- Almost every model here assumes assets are being compared on the same basis.

### 2. Covariance estimation

The app uses a Ledoit-Wolf covariance estimator by default.

Plain English:

- Covariance tells us how assets move together.
- Simple covariance can get noisy when the history is limited.
- Ledoit-Wolf "shrinks" the estimate to make it more stable and less fragile.

Why this matters:

- Optimization and Monte Carlo both depend heavily on covariance quality.

### 3. Hidden Markov Model regime detection

The regime detector is a Gaussian HMM trained on `SPY` returns.

Plain English:

- Markets do not always behave the same way.
- Sometimes they are strong and rising, sometimes mixed, sometimes stressed.
- The HMM tries to sort market behavior into three hidden states:
  - `bull`
  - `sideways`
  - `bear`

What the app does with it:

- It predicts the current regime.
- It scales covariance differently depending on that regime.
- Bear-like regimes increase effective risk; bull-like regimes soften it.

### 4. Black-Litterman

Black-Litterman blends market-implied returns with optional views.

Plain English:

- A plain optimizer can become unstable if you feed it raw return guesses.
- Black-Litterman starts with a calm "baseline belief" implied by the market and covariance.
- Then it gently adjusts that baseline using:
  - user views such as "AAPL should return 8%"
  - optional momentum-model forecasts
  - confidence values that say how strongly to trust those views

Why it is useful:

- It produces expected returns that are usually less extreme than naive forecasting.

### 5. Constrained mean-variance optimization

After expected returns and covariance are ready, the app runs constrained MVO with CVXPY.

Plain English:

- The optimizer is trying to find a set of weights that balances return and risk.
- `risk_tolerance = 0` leans toward low variance.
- `risk_tolerance = 1` leans toward higher expected return.
- The app also obeys asset-class limits, such as:
  - crypto max 20%
  - bonds min 10%

Why it is useful:

- It turns abstract preferences into an actual target allocation.

### 6. Efficient frontier

The efficient frontier is built by rerunning optimization across many risk-tolerance values.

Plain English:

- Instead of showing only one answer, the app shows a whole curve of tradeoffs.
- Each point says: "If you accept this amount of risk, here is a portfolio with a matching expected return profile."

Why it is useful:

- It helps users understand the tradeoff between being safer and aiming higher.

### 7. Momentum forecasts

The momentum model is an optional return forecaster: a scikit-learn regressor trained offline and loaded from `backend/models/momentum_model.pkl`.

Plain English:

- It looks at recent weekly price momentum: mean and volatility of the last 4 and 8 weeks, how many of those weeks were positive, and the worst 4-week drop.
- It predicts a forward return from that pattern, then blends it with the asset's own historical return and a long-term asset-class prior so the ML signal alone can never dominate the estimate.
- The prediction is clipped to asset-class-specific bounds before it ever reaches Black-Litterman, so an extreme forecast can't destabilise the optimizer.

Important reality check:

- The app does not train this model live in production; it's loaded read-only from the committed `.pkl` file.
- If the model file is missing, the rest of the optimization pipeline still works -- optimization simply continues without those forecast views.

### 8. Monte Carlo simulation

The risk module simulates many possible future portfolio paths using correlated random draws.

Plain English:

- Instead of predicting one future, it creates many possible futures.
- It respects how assets tend to move together.
- From those simulated paths, the app estimates:
  - median outcome
  - upside / downside bands
  - probability of ending below today's value

Why it is useful:

- It gives a scenario range, not just a single number.

### 9. VaR and CVaR

These are downside-risk measures built from historical portfolio returns.

Plain English:

- VaR answers: "How bad could a normal bad day get at this confidence level?"
- CVaR answers: "If we are already in the bad tail, how bad is the average outcome there?"

Quick intuition:

- VaR is the threshold.
- CVaR is the average pain beyond the threshold.

### 10. Sharpe, Sortino, Calmar, beta, and drawdown

These are standard portfolio quality metrics.

- Sharpe ratio: return earned per unit of total volatility
- Sortino ratio: return earned per unit of downside volatility
- Calmar ratio: annual return relative to maximum drawdown
- Beta: how sensitive the portfolio is to the market benchmark
- Max drawdown: worst peak-to-trough drop over the observed period

### 11. Fama-French 5-factor model

The analytics module runs an OLS regression of portfolio excess returns on the five Fama-French factors.

Plain English:

- Instead of saying "the portfolio went up," this model asks why.
- It estimates how much performance behaves like exposure to:
  - market risk
  - small-cap tilt (`SMB`)
  - value tilt (`HML`)
  - profitability (`RMW`)
  - conservative investment style (`CMA`)

Why it is useful:

- It tells you whether returns are coming from broad market exposure or from factor tilts.

## Backtesting & Adaptive Strategy Selection

The rest of this document describes the *live* pipeline: every request fetches current data (through the Redis cache) and answers "what should I do right now?" The Backtest page answers a different question -- "if I had been using this pipeline for the last several years, would it actually have worked?" -- and it is intentionally built on a separate, explicitly historical data path so that answering it doesn't put any extra load on the live request path or the free-tier market data APIs.

### Historical dataset cache

`backend/quant/backtest_data.py` fetches each backtest-universe asset's full price history once via the existing `DataFetcher` and stores it as a local parquet file under `backend/data/historical/` (git-ignored, regenerable). Every later call only fetches the days missing since the last update instead of re-downloading years of history. Build or refresh it with:

```bash
cd backend
python -m backend.scripts.build_backtest_dataset
```

The fixed multi-asset universe (spanning stocks, ETFs, gold, bonds, and crypto across US and Indian markets) lives in `backend/quant/backtest_universe.py`.

### Walk-forward engine

`backend/quant/backtest.py` replays the same building blocks used by the live optimizer -- Ledoit-Wolf shrinkage, Black-Litterman blending, HMM regime scaling, constrained MVO -- against the cached history with monthly rebalancing and a strict no-lookahead window: at each rebalance date, a strategy only ever sees returns strictly before that date. Four strategies are compared: `equal_weight`, `static_mvo` (raw sample covariance), `mvo_ledoit_wolf` (shrinkage only), and `full_pipeline` (the actual production default: BL + LW + HMM). A flat transaction cost (basis points on turnover) is applied at each rebalance.

### Adaptive regime-conditioned bandit

`backend/quant/strategy_bandit.py` adds a fifth, adaptive strategy: a Thompson-Sampling contextual bandit whose context is the detected HMM regime (bull/sideways/bear) and whose arms are `static_mvo` / `mvo_ledoit_wolf` / `full_pipeline`. It learns purely from the walk-forward replay's own realized, volatility-normalized rewards -- never from future information -- which strategy has actually worked best in each regime so far, and prefers that one going forward. It is deliberately a small, inspectable posterior table rather than a black-box deep-RL policy.

### Statistics

`backend/quant/backtest_stats.py` computes per-strategy CAGR/Sharpe/Sortino/Calmar/max-drawdown/VaR/CVaR (reusing the existing `risk_engine.py` helpers), a regime-conditional breakdown of those same metrics, and a block-bootstrap confidence interval on the Sharpe-ratio difference between each strategy and a chosen baseline -- so an improvement can be reported as statistically supported (or honestly reported as not yet significant) rather than asserted from a single anecdotal run.

### API and page

`GET /api/v1/backtest/` (query params: `lookback_days`, `transaction_cost_bps`, `baseline`) runs the above against the local cache and returns per-day equity curves, the metrics table, the regime breakdown, the bootstrap significance results, and the bandit's posterior. The `/backtest` frontend page visualizes all of it: equity curves, a drawdown chart with a regime timeline, the significance panel, and a full comparison table.

## Tax-Aware Rebalancing (India)

Every strategy above optimizes pre-tax returns, same as the finance literature it's built on. That's a real gap for Indian investors specifically: a rupee of gain isn't worth the same regardless of *how* it's realized. Equity/MF gains are taxed at 20% if held under a year, 12.5% (over a Rs 1.25L annual exemption) if held longer. Debt/bond funds lost long-term treatment entirely after the FY2023-24 reclassification -- always slab rate, no matter how long they're held. Gold gets a 24-month long-term threshold. Crypto is the sharpest case: a flat 30% on every gain under Section 115BBH, and losses can offset **nothing** -- not other income, not even a gain on a different coin, and they can't be carried forward. A rebalance that ignores all of this can pay materially more tax than one that doesn't, with zero change to the underlying investment strategy -- purely from *which lot* gets sold.

### Tax rules

`backend/quant/tax_rules.py` encodes the rates and holding-period thresholds above (Union Budget 2024 law) and `TaxYearTracker` handles the two stateful parts real capital gains calculations require: the Rs 1.25L equity/MF long-term exemption is an *annual aggregate*, not a per-trade allowance, and short-/long-term capital losses can offset later gains within the same Indian fiscal year (1 April - 31 March) under the standard set-off ordering. These are representative rates for measuring the *structural* effect of asset-class- and holding-period-dependent taxation, not a substitute for professional tax advice -- Indian tax law is revised most fiscal years, and real liability also depends on the investor's income slab, surcharge, and cess, none of which are modeled here.

### Lot ledger and lot-selection policies

`backend/quant/tax_lot_ledger.py` simulates a real position ledger -- individual tax lots with quantity, acquisition date, and cost basis -- since tax depends on exactly which lot is sold, not just the aggregate weight change. Two lot-selection policies execute the *same* target-weight rebalance differently: `fifo` (oldest lot first, what a tax-blind rebalancer or brokerage default produces) and `tax_aware` (ranks lots by their tax cost right now: loss lots first since realizing them is free, then the lowest-rate gains, deferring the largest gains). For crypto specifically, `tax_aware` still prefers loss lots first even though the loss provides no offset benefit -- it's free to realize, so it's the cheapest lot available, which is exactly the behavior a naive policy misses.

### Tax-aware backtest

`backend/quant/tax_aware_backtest.py` replays a strategy's *already-computed* walk-forward target weights (default: `full_pipeline`, unchanged) through the lot ledger under three policies: a frictionless `no_tax` baseline, `fifo`, and `tax_aware`. The `no_tax` baseline uses identical trade sizing and ledger mechanics as `fifo` with tax switched off, so tax is the only isolated variable -- comparing against the walk-forward engine's own equity curve instead would also pick up its separate transaction-cost convention and mislabel the result. On the cached universe (~8 years, `full_pipeline`), naive FIFO rebalancing costs roughly 1.8-2.5% cumulative tax drag versus the frictionless baseline, and tax-aware lot selection recovers about a third of that -- with zero change to the investment strategy itself. The live universe currently lacks enough crypto history to demonstrate the no-offset case with real cached prices (CoinGecko's free tier only returns partial history); `backend/tests/test_tax_lot_ledger.py` and `test_tax_aware_backtest.py` demonstrate it precisely with synthetic data instead.

### API and page

The tax comparison is included in the `GET /api/v1/backtest/` response as `tax_comparison` (equity curves per policy, tax paid by asset class, and the naive-drag/tax-aware-savings/recovery percentages). The `/backtest` page's "Tax-Aware Rebalancing" section visualizes it.

## Data Model

### Core tables

- `users`: authenticated users
- `assets`: master list of supported instruments and their metadata
- `portfolios`: user portfolios with base currency and allocation constraints
- `holdings`: positions inside each portfolio

### Important schema concepts

- A holding stores `ticker`, `quantity`, `avg_buy_price`, and `buy_currency`.
- An asset stores `asset_class`, `exchange`, `currency`, and `data_source`.
- A portfolio stores per-asset-class min/max bounds in JSON.

## API Overview

All routes currently live under `/api/v1`.

### Auth

- `POST /api/v1/auth/register` sets the auth cookie and returns the created user
- `POST /api/v1/auth/token` sets the auth cookie and returns the authenticated user
- `GET /api/v1/auth/me`
- `POST /api/v1/auth/logout` clears the auth cookie

### Portfolios and holdings

- `POST /api/v1/portfolios/`
- `GET /api/v1/portfolios/`
- `GET /api/v1/portfolios/{portfolio_id}`
- `PATCH /api/v1/portfolios/{portfolio_id}`
- `DELETE /api/v1/portfolios/{portfolio_id}`
- `POST /api/v1/portfolios/{portfolio_id}/holdings`
- `GET /api/v1/portfolios/{portfolio_id}/holdings`
- `DELETE /api/v1/portfolios/{portfolio_id}/holdings/{holding_id}`

### Assets

- `GET /api/v1/assets/`
- `POST /api/v1/assets/`
- `GET /api/v1/assets/{ticker}`
- `PATCH /api/v1/assets/{ticker}`
- `DELETE /api/v1/assets/{ticker}`

### Quant endpoints

- `POST /api/v1/optimize/`
- `GET /api/v1/risk/{portfolio_id}`
- `GET /api/v1/risk/{portfolio_id}/monte-carlo`
- `GET /api/v1/analytics/{portfolio_id}`
- `GET /api/v1/analytics/{portfolio_id}/factors`
- `GET /api/v1/backtest/` -- walk-forward strategy comparison (see "Backtesting & Adaptive Strategy Selection" above)

### Health

- `GET /health`

## Local Development Setup

### Zero-dependency quickstart (verified working)

If you just want to clone this and see it run -- no Postgres, no Redis, no Docker, no `.env` file at all -- this path has been tested end-to-end from a genuinely fresh clone:

```bash
# Backend
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows; use `source .venv/bin/activate` on macOS/Linux
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`, register an account, and use the app. No database or cache setup needed: `DATABASE_URL`'s default points at a local Postgres that (on a fresh machine) won't exist, so `backend/main.py`'s startup automatically falls back to a local SQLite file (`backend/quantportfolio.db`); Redis does the same thing, falling back to an in-memory cache. Both fallbacks are logged clearly at startup so you always know which one is active. This is the fastest way to confirm the app runs correctly on a new device -- for a setup closer to the real deployment target (Postgres + Redis), see the full setup below or the Docker Compose option.

### 1. Prerequisites

You will need:

- PostgreSQL running locally
- Redis running locally, or willingness to use the in-memory cache fallback
- Python for the backend
- Node.js and npm for the frontend

Recommended supporting tools:

- a Python virtual environment
- `psql` or another Postgres client

### 2. Backend environment

Create `backend/.env` with values like these:

```env
# App
SECRET_KEY=replace-with-a-long-random-secret
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
DEBUG=false

# Database
DATABASE_URL=postgresql+asyncpg://postgres:password@localhost:5432/quantportfolio

# Redis
REDIS_URL=redis://localhost:6379

# External APIs
ALPHA_VANTAGE_KEY=demo
COINGECKO_BASE=https://api.coingecko.com/api/v3
YAHOO_BASE=https://query1.finance.yahoo.com/v8/finance
AMFI_NAV_URL=https://www.amfiindia.com/spages/NAVAll.txt

# Quant
RISK_FREE_RATE=0.065
MVO_ROLLING_WINDOW_DAYS=252
HMM_N_STATES=3
MONTE_CARLO_PATHS=1000
MONTE_CARLO_HORIZON_DAYS=252
CVAR_CONFIDENCE=0.95
```

### Important settings

- `DATABASE_URL`: async SQLAlchemy connection string
- `REDIS_URL`: cache backend
- `SECRET_KEY`: JWT signing secret
- `RISK_FREE_RATE`: used in Sharpe-like calculations and optimizer scoring

### 3. Install backend dependencies

```bash
cd backend
pip install -r requirements.txt
```

### Extra packages you may also need

Some helper scripts rely on packages that are not listed in `backend/requirements.txt` at the moment.

- `python-dotenv` for Alembic env loading and `seed_assets.py`
- `psycopg2` or `psycopg2-binary` for Alembic's sync migration URL
- `fakeredis` if you want to run `dev_fake_redis.py`

Example:

```bash
pip install python-dotenv psycopg2-binary fakeredis
```

### 4. Create the database and run migrations

Create a Postgres database named `quantportfolio`, then run:

```bash
cd backend
alembic upgrade head
```

### 5. Optional: run fake Redis

If you do not want to run a real Redis instance, there are two relevant behaviors:

- the main app already falls back to an in-memory cache if Redis is unavailable
- there is also a helper script:

```bash
cd backend
python dev_fake_redis.py
```

That helper uses `fakeredis` and listens on `127.0.0.1:6379`.

### 6. Start the backend

```bash
cd backend
uvicorn main:app --reload --port 8000
```

Backend health check:

```bash
curl http://localhost:8000/health
```

### 7. Frontend environment

The frontend reads:

```env
VITE_API_URL=http://localhost:8000
```

If you do not set it, the Axios client already defaults to `http://localhost:8000`.

### 8. Install and run the frontend

```bash
cd frontend
npm install
npm run dev
```

Open:

- `http://localhost:5173`

### 9. Docker deployment

If you want the full stack in one command, use Docker Compose from the repository root. It reads its backend environment from a root-level `.env` file, so create one first:

```bash
cp backend/.env.example .env
```

Then edit `.env` so `DATABASE_URL` points at the `db` service name (not `localhost`) -- Docker Compose's internal network resolves service names, not your host machine's `localhost`:

```env
DATABASE_URL=postgresql+asyncpg://quantportfolio:quantportfolio@db:5432/quantportfolio
```

Then:

```bash
docker compose up --build
```

That starts:

- PostgreSQL on `localhost:5432`
- Redis on `localhost:6379`
- FastAPI on `localhost:8000`
- nginx serving the Vite build on `http://localhost:8080`

The frontend is wired to call the backend on `http://localhost:8000`, and the backend CORS list already allows the Docker frontend origin.

### 10. First-run flow

Once both apps are running:

1. Register a user.
2. Finish onboarding to create your first portfolio.
3. Add holdings from the seeded asset list.
4. Open Dashboard, Risk, Analytics, and Optimize.

## Frontend Workflow Notes

### State management

- JWT token is stored in `localStorage` as `qp_token`
- onboarding completion is stored as `qp_onboarded`
- active portfolio ID and selected regime are stored in Zustand state

### Data fetching

- Axios handles auth headers automatically
- a global 401 handler clears the token and redirects to `/login`
- the app mounts a React Query provider, but the current page hooks mostly use custom `useEffect` + `useState` fetching rather than React Query hooks

### UI pages

- `Dashboard`: value, PnL, allocation, performance, risk snapshot, top holdings
- `Holdings`: search, filter, add, delete, and inspect positions
- `Optimize`: set risk tolerance, class constraints, user views, and model toggles
- `Risk`: inspect VaR/CVaR, Monte Carlo ranges, correlation, and supporting ratios
- `Analytics`: inspect factor exposure plus return/risk attribution

## Scheduled Jobs

`backend/tasks/scheduler.py` defines two recurring jobs:

- hourly cache invalidation for prices and FX
- weekly refit of the regime detector on Sunday at 02:00

The momentum forecaster is not retrained on a schedule; it's a static, offline-trained model loaded once at startup.

## Asset Seeding

There are two seeding paths:

- app startup automatically seeds a compact default asset list through `seed_default_assets`
- `backend/seed_assets.py` provides a larger one-off seeding script with a broader asset universe

That means the app is usable immediately after startup, but you can expand the available search universe later if you want.

## Testing

### Backend tests

```bash
pytest backend/tests
```

Current backend tests cover:

- Black-Litterman equilibrium behavior
- constrained MVO respecting class bounds
- VaR / CVaR / drawdown utilities
- Monte Carlo output shape
- Fama-French regression output
- asset router behavior

### Frontend tests

```bash
cd frontend
npm run test
```

Current frontend coverage is minimal and mainly verifies test wiring.

### Useful additional checks

```bash
cd frontend
npm run lint
npm run build
```

## Practical Caveats And Implementation Notes

This section matters if you want to understand the repo as it really exists today, not as a generic quant app.

### What is already solid

- clear separation between routers, services, schemas, and quant modules
- good reuse of aligned return data across features
- startup seeding makes local onboarding easier
- Redis cache failure does not stop the app from functioning

### Things to know before extending it

- CORS origins are currently hardcoded in `backend/main.py` for local dev hosts even though `ALLOWED_ORIGINS` exists in settings.
- The regime detector is trained from `SPY` history and optimization currently uses the first aligned return series as the market proxy when predicting the live regime.
- The momentum forecaster is optional. A missing model file does not break the API; optimization simply continues without those forecast views.
- Portfolio `base_currency` exists in the data model, but major calculations are normalized internally and many user-facing analytics are rendered in INR.
- The onboarding asset-class picker influences the initial user experience, but the persisted portfolio creation step currently stores name, description, base currency, and risk-profile constraints rather than a hard investable-universe filter.
- The frontend includes a React Query provider, but most current hooks are handwritten async hooks instead of React Query-powered caches.
- Helper scripts and migration tooling need a couple of extra Python packages that are not pinned in `backend/requirements.txt` yet.

## Suggested Development Reading Order

If you are new to the codebase, this is the fastest way to understand it:

1. `backend/main.py`
2. `backend/config.py`
3. `backend/routers/`
4. `backend/services/`
5. `backend/quant/`
6. `frontend/src/App.tsx`
7. `frontend/src/pages/`
8. `frontend/src/hooks/`
9. `frontend/src/lib/portfolioMappers.js`

## Short Summary

QuantPortfolio is not just a CRUD app with charts. It is a portfolio workflow where:

- holdings are the source of truth
- market data is fetched and cached centrally
- returns are normalized into a comparable matrix
- that matrix powers optimization, risk, simulation, and factor decomposition
- the frontend turns those outputs into an investor-facing workflow

If you want a single sentence version: this repo is a portfolio intelligence dashboard with a FastAPI quant engine behind it.
