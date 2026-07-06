# QuantPortfolio

## Overview

QuantPortfolio is a full-stack portfolio intelligence platform. You enter your holdings (stocks, crypto, gold, ETFs/mutual funds, bonds), it fetches live market data, normalizes everything into comparable return series, and then runs institutional-grade quantitative analysis: mean-variance optimization with Black-Litterman, regime-aware Monte Carlo simulation, VaR/CVaR risk decomposition, and Fama-French 5-factor attribution. The results are presented through a React dashboard with interactive charts.

### Why it exists

Most retail portfolio tools show you what you own. This one tells you *why* your portfolio behaves the way it does, what an optimal rebalance would look like under current market conditions, and how bad things could get statistically. The backend is designed so every quant module reuses the same aligned return matrix — optimization, risk, simulation, and factor analysis all start from the same data pipeline, which keeps results consistent.

### Architecture

```
React/Vite frontend (SPA)
  → Axios API client (cookie-based JWT auth)
  → FastAPI backend (async, Pydantic v2 schemas)
    → Service layer (business logic, portfolio snapshots)
    → Quant engine (returns → covariance → expected returns → optimizer/risk/MC/factors)
    → Market data fetcher (Yahoo Finance, CoinGecko, AMFI, Ken French) + Redis cache
    → SQLAlchemy async engine → PostgreSQL (with SQLite fallback)
    → APScheduler (cache refresh, regime refit, portfolio monitoring)
```

### Data flow for a typical optimization request

1. Frontend POSTs to `/api/v1/optimize/` with portfolio ID, risk tolerance, constraints, optional user views, and model toggles
2. Router validates via Pydantic, passes to `optimization_service.run_optimization()`
3. Service calls `load_portfolio_snapshot()` → fetches holdings + asset metadata from DB
4. `DataFetcher` fetches price history for each ticker (Yahoo/CoinGecko) with Redis caching + tenacity retries
5. `align_returns()` converts prices to log returns, applies FX normalization (INR→USD via live rate), aligns dates
6. `RegimeDetector.detect_regime()` classifies current market as bull/sideways/bear using HMM + volatility + trend signals
7. `compute_covariance()` estimates Ledoit-Wolf shrinkage covariance, then `shrink_volatility()` blends per-asset vol toward class targets
8. `scale_covariance_by_regime()` scales diagonal/off-diagonal based on regime
9. `blend_expected_returns()` produces daily expected returns by blending equilibrium, historical, ML, and momentum signals with regime-dependent weights
10. If user views exist, `black_litterman_returns()` adjusts expected returns via BL posterior
11. `constrained_mvo()` solves via CVXPY with asset-class bounds + per-asset cap
12. `efficient_frontier()` sweeps risk tolerance [0, 1] to produce 50 frontier points
13. Live INR prices are fetched for rebalance trade deltas
14. Response DTO includes optimal weights, frontier, regime label, Sharpe, and rebalance trades

### Current status

| Feature | Status | Evidence |
|---|---|---|
| User auth (register/login/logout/me) | ✅ Fully working | JWT cookie-based, bcrypt hashing, all 4 endpoints wired |
| Portfolio CRUD | ✅ Fully working | Create, list, get, update, delete — with cascade delete of holdings |
| Holding management + upsert | ✅ Fully working | Add, bulk-add, list, delete — with weighted-average merge on duplicate ticker |
| Asset search + seeding | ✅ Fully working | 13 default assets seeded on startup; search by ticker/name, filter by class |
| Onboarding wizard | ✅ Fully working | 6-step investor profiling → risk score → auto-create portfolio with calibrated constraints → recommended holdings with live prices |
| Optimization (BL + MVO + frontier) | ✅ Fully working | Full pipeline with regime scaling, user views, LSTM forecasts, efficient frontier |
| Risk metrics (VaR, CVaR, Sharpe, etc.) | ✅ Fully working | Historical VaR/CVaR at 95%/99%, drawdown, Sharpe, Sortino, Calmar, beta |
| Monte Carlo simulation | ✅ Fully working | Regime-switching GBM with Student-t tails, jump diffusion, Cholesky correlation |
| Factor analysis (FF5) | ✅ Fully working | OLS regression on Ken French daily factors, annualized alpha and betas |
| Analytics (PnL, allocation, performance) | ✅ Fully working | Day/total PnL in USD+INR, sparklines, return/risk attribution, benchmark comparison |
| Portfolio monitoring + alerts | ✅ Fully working | Drift detection, peak drawdown alerts, market-hours + EOD scheduled scans |
| Alert notification system | ✅ Fully working | CRUD for alerts, auto-generated on holding change drift, navbar badge in frontend |
| Background re-optimization | ✅ Fully working | `BackgroundTasks` re-optimizes after every holding add/delete, stores drift alerts |
| HMM regime detector | ✅ Fully working | Trained on SPY, 3-signal composite (HMM 50%, vol 30%, trend 20%), with GMM fallback |
| Momentum forecaster (sklearn) | ✅ Fully working | `momentum_model.pkl` present in `models/`, loaded by `ReturnForecaster.load()` |
| LSTM forecaster (PyTorch) | ✅ Weights present | `lstm_latest.pt` exists; loaded on startup; offline training via `ml/trainer.py` |
| Scheduled jobs | ✅ Fully working | 5 cron jobs: hourly cache flush, weekly regime refit, monthly LSTM reminder, market-hours monitor, EOD monitor |
| Docker deployment | ✅ Fully working | docker-compose with Postgres 16, Redis 7, FastAPI, nginx-fronted Vite build |
| Database migrations | ✅ Fully working | 4 Alembic migrations: initial schema, investor profiles, monitoring columns, alerts |
| SQLite fallback | ✅ Fully working | If Postgres is unreachable, lifespan auto-switches to `aiosqlite` at project root |
| Frontend (all pages) | ✅ Fully working | Dashboard, Holdings, Optimize, Risk, Analytics, Onboarding, Login, Register |
| Frontend tests | ⚠️ Minimal | Vitest wired, `portfolioMappers.test.ts` exists, but no page/component tests |
| Backend tests | ✅ Good coverage | 16 test files covering quant modules, services, routers, and integration |
| Rate limiting | ✅ Wired | slowapi on optimize endpoint (5/min); limiter middleware installed globally |

#### Dead code / partial items flagged

- `utils/format.py`: Contains `format_inr()` — **not imported anywhere** in the codebase. Dead code.
- `seed_assets.py`: Standalone script with a larger asset universe — works but **not integrated** into the app startup or any route; must be run manually.
- `dampen_crypto_volatility()` in `covariance.py`: Legacy alias, delegates to `shrink_volatility()`. Not called by any active code path — only `shrink_volatility` is used directly.
- `compute_correlation_matrix()` in `covariance.py`: Exported but **never called** from any service or quant module.
- `annualise_returns()`, `annualise_geometric_return()`, `annualise_volatility()` in `returns.py`: Exported but **never called** — the risk engine has its own identical private implementations (`_annualised_arithmetic_return`, `_annualised_geometric_return`, `_annualised_volatility`).
- `lib/mockData.js` in frontend: Contains hardcoded mock data — **not imported** by any page or component. Test/dev artifact.
- React Query provider is mounted in `App.tsx`, and `useRisk`, `useAnalytics`, `useAuth`, `useAlerts`, and `useOptimize` all use React Query. The older `usePortfolios` and `useHoldings` hooks still use manual `useEffect` + `useState` pattern (not React Query). Both patterns work, but they are inconsistent.
- `BNB` is in the CoinGecko ID map as a default asset but has **no CoinGecko ID mapping** in `COINGECKO_ID_MAP` — it will fall back to Yahoo via `_fetch_yahoo_crypto_fallback` (which maps `BNB` → `BNB-USD`). This works but is an implicit fallback, not an explicit mapping.

### Tech stack

| Layer | Technologies |
|---|---|
| Frontend | React 18, Vite 5, TypeScript + JSX mix, React Router 6, Tailwind CSS, shadcn/ui, Radix UI, Recharts, Zustand, React Query, Axios |
| Backend API | FastAPI, Pydantic v2, Uvicorn, slowapi (rate limiting) |
| Database | PostgreSQL 16 (primary) with SQLAlchemy async engine + Alembic; SQLite via aiosqlite (fallback) |
| Cache | Redis 7 via `redis.asyncio`, with transparent in-memory dict fallback |
| Quant / math | NumPy, Pandas, SciPy (implicit via sklearn), scikit-learn (Ledoit-Wolf, GMM), CVXPY, hmmlearn, statsmodels, joblib |
| ML | PyTorch (LSTM), scikit-learn (momentum model) |
| Auth | python-jose (JWT), Passlib (bcrypt) |
| Data sources | Yahoo Finance v8 chart API, CoinGecko v3, AMFI mutual fund NAV, Ken French data library, NSE equity quotes, Open Exchange Rates (FX fallback) |
| Reliability | httpx (async HTTP), tenacity (retry with exponential backoff) |
| Scheduling | APScheduler (async) |
| Deployment | Docker Compose (Postgres, Redis, FastAPI, nginx) |

---

## Interview Deep-Dive Reference

### 1. Return Alignment and FX Normalization (`quant/returns.py`)

**What it does**: Converts raw price DataFrames from multiple assets into a single aligned DataFrame of daily log returns in a common currency.

**Why it exists**: Every downstream module (optimization, risk, Monte Carlo, factors) needs returns that are comparable across assets. If one holding is priced in INR and another in USD, comparing raw returns is meaningless. This module is the single normalization point.

**Key functions**:

- `log_returns(prices: Series) → Series`: Computes `ln(P_t / P_{t-1})`. Uses log returns throughout because they are additive over time and better behaved for the math that follows (covariance estimation, GBM simulation).
- `align_returns(price_data, asset_currencies, base_currency, usd_inr_rate) → DataFrame`: Takes a dict of ticker→DataFrame, divides INR prices by the USD/INR rate (or multiplies USD prices by it), computes log returns for each, then joins on date and drops any row with a NaN in any column.

**Why log returns instead of simple returns**: Log returns are additive across time, which makes them natural for covariance estimation, GBM simulation (which operates in log-space), and the Jensen's inequality corrections applied later. The codebase consistently applies the `+0.5σ²` correction when converting back to arithmetic returns for reporting.

**Non-obvious choice**: The `dropna(how="any")` in `align_returns` means the final matrix only includes dates where *every* asset traded. This loses some data but guarantees the covariance matrix is computed on aligned observations — using `fillna(0)` or forward-fill would introduce fake zero-return days that distort correlation estimates.

**Tricky part**: The FX conversion is applied to prices *before* computing returns, not to returns themselves. This is correct because `ln((P_t / FX) / (P_{t-1} / FX)) = ln(P_t / P_{t-1})` when FX is constant, but in reality FX moves daily. The code uses a single static `usd_inr_rate` rather than a daily FX series, which is a simplification — it correctly converts levels but ignores intra-period FX volatility.

---

### 2. Covariance Estimation (`quant/covariance.py`)

**What it does**: Estimates the covariance matrix of asset returns with shrinkage, volatility normalization, and regime-aware scaling.

**Why it exists**: Raw sample covariance is noisy with limited data and can produce unstable optimization results. This module applies three layers of stabilization.

**Key functions**:

- `compute_covariance(returns, method, annualise, trading_days) → ndarray`: Supports three estimators:
  - `ledoit_wolf` (default): Optimal linear shrinkage. Chosen because it automatically balances between the noisy sample covariance and a structured target. No hyperparameter tuning needed.
  - `ewm`: Exponentially-weighted with span=60. More responsive to recent regime changes, but noisier.
  - Sample covariance (fallback).
  
  Always calls `_ensure_psd()` at the end.

- `shrink_volatility(cov, asset_classes, annualised, trading_days) → ndarray`: Instead of hard-capping volatility (which breaks the correlation structure), applies `σ_adj = α·σ_raw + (1-α)·σ_target` per asset, then rescales the covariance row and column to match the new volatility while preserving correlations exactly. The rescaling is: multiply row `i` and column `i` by `ratio = shrunk_vol / raw_vol`, then fix the diagonal (which got scaled twice) to `shrunk_vol²`.

  **Why this over hard clipping**: If you clip crypto vol from 80% to 55%, the correlation between crypto and stocks gets distorted because `cov(i,j) = ρ·σ_i·σ_j`. The shrinkage approach preserves ρ exactly.

- `scale_covariance_by_regime(cov, regime_state, diag_scale, offdiag_scale) → ndarray`: In bear markets, scales diagonal by 1.4× (assets get more volatile) and off-diagonal by 1.5× (correlations increase — the "correlations go to 1 in a crash" effect). In bull markets, dampens both.

- `_ensure_psd(matrix) → ndarray`: If any eigenvalue is negative, adds `(-min_eigenvalue + ε)·I`. This is a standard nearest-PSD fix needed because shrinkage + scaling can sometimes push the matrix slightly out of PSD territory.

**Non-obvious choices**:
- The volatility targets (crypto: 55%, stock: 22%, bond: 6%) and shrinkage intensities (crypto gets α=0.45, meaning 55% pull toward target; bonds get α=0.80, keeping 80% of raw vol) are calibrated heuristics, not learned parameters. They encode the prior that crypto vol estimates from 1 year of data are unreliable and should be regularized more aggressively.
- Using `sklearn.covariance.LedoitWolf` over the analytical Ledoit-Wolf formula — sklearn's implementation handles edge cases (singular matrices, too few observations) that a hand-rolled version would need to handle manually.

---

### 3. Expected Returns Engine (`quant/expected_returns.py`)

**What it does**: Produces a daily expected return vector by blending four signals with regime-dependent weights.

**Why it exists**: Naive expected returns (just historical mean) are extremely noisy and lead to concentrated, unstable portfolios. This engine anchors to equilibrium returns and only deviates proportionally to signal confidence.

**The blending formula**:
```
μ_final = w₁·Π_eq + w₂·μ_hist + w₃·μ_ML + w₄·μ_views + momentum_adj
```

**Key functions**:

- `compute_equilibrium_returns(cov, market_weights, risk_aversion, rf) → ndarray`: Computes `Π = δΣw_mkt + Rf + 0.5σ²`. The `+0.5σ²` (Jensen's term) is critical — it converts from log-space equilibrium returns to arithmetic expected returns. Without this, when Monte Carlo applies its own Itô correction (`-0.5σ²`), the net log-drift would be too low, causing structurally negative simulated paths.

- `compute_historical_returns(returns_df, asset_classes, shrinkage_strength) → ndarray`: Computes daily log-return means, adds Jensen's correction (`+0.5·var`), annualizes, then Bayesian-shrinks toward long-term priors (stocks: 11%, crypto: 8%, bonds: 6.5%). Adaptive shrinkage: with <2 years of data, pulls more toward priors; with >2 years, trusts the data more.

- `compute_momentum_adjustment(returns_df, lookback_short, lookback_long, momentum_weight) → ndarray`: If short-term (21-day) and medium-term (126-day) trends agree in sign, adds up to ±3% annualized tilt. If they diverge, partially reverses (mean-reversion signal). Capped at ±3% annualized to prevent momentum from dominating.

- `blend_expected_returns(...) → (mu_daily, diagnostics)`: Loads the regime profile (bull/sideways/bear), computes all four signal vectors, blends with regime weights, adds momentum, then applies the Itô-aware floor. Returns both the vector and a diagnostics dict for debugging.

  **The regime profiles**:
  - Bull (state 0): equilibrium 30%, historical 30%, ML 25%, views 15%, risk_aversion ×0.80
  - Sideways (state 1): equilibrium 50%, historical 20%, ML 15%, views 15%, risk_aversion ×1.00
  - Bear (state 2): equilibrium 50%, historical 15%, ML 10%, views 25%, risk_aversion ×1.30

- `compute_market_weights_from_volatility(cov) → ndarray`: Uses inverse-volatility weighting as a market-cap proxy. Lower-vol assets (bonds, gold) get higher weight, mimicking the fact that in global capital markets, stable asset classes represent a larger share of total wealth. This is used as `w_mkt` in the BL equilibrium calculation.

**Tricky part — the Itô floor** (lines 223-235): After blending, the code enforces a per-asset minimum: `mu_arith ≥ scale·Rf + 0.5·σ²`. The `0.5σ²` term is there because Monte Carlo will subtract it during simulation (Itô correction). Without this floor, high-volatility assets (crypto with σ²/day ≈ 0.003) would end up with negative log-drift in the simulation, causing systematically declining paths even in a bull market. The floor is regime-dependent: bull uses full Rf, bear uses 10% of Rf.

---

### 4. Black-Litterman (`quant/black_litterman.py`)

**What it does**: Blends investor views (or ML forecasts) with equilibrium returns using the Black-Litterman formula.

**Why it exists**: Raw expected return estimates lead to extreme portfolio concentrations. BL starts from a stable equilibrium baseline and only tilts away from it proportionally to view confidence.

**Key functions**:

- `implied_equilibrium_returns(cov, market_weights, risk_aversion) → ndarray`: Computes `Π = δΣw`. This is the "what would the market believe" return vector.

- `build_omega_from_confidence(P, cov, tau, confidences) → ndarray`: Builds the view uncertainty matrix Ω. For each view, `Ω_ii = (p_i·(τΣ)·p_i') · (1-c)/c` where c is confidence. Higher confidence → smaller Ω → view pulls harder. This is the Meucci confidence calibration approach.

- `black_litterman_returns(inputs: BLInputs) → ndarray`: Implements the BL master formula: `μ_BL = (τΣ⁻¹ + P'Ω⁻¹P)⁻¹ · (τΣ⁻¹·Π + P'Ω⁻¹·Q)`. Uses `_regularized_inverse` which adds `1e-8·I` jitter on `LinAlgError` to handle near-singular matrices.

- `posterior_covariance(inputs) → ndarray`: Returns `(τΣ⁻¹ + P'Ω⁻¹P)⁻¹`, which is added to the prior covariance in the optimization service to form the posterior covariance used for MVO.

**Non-obvious choice**: `tau = 0.025` (set in `optimization_service.py`). Literature suggests τ ∈ [0.01, 0.05]. Lower τ means less uncertainty about equilibrium, so views need more confidence to shift returns. 0.025 is a moderate choice.

**How views enter the system**: Users specify views as `{ticker, expected_return, confidence}`. The router maps these into P (pick matrix — one row per view, a 1 in the column of the target ticker) and Q (view return vector). The optimization service only calls BL if at least one valid view exists.

---

### 5. Constrained Mean-Variance Optimization (`quant/mvo.py`)

**What it does**: Solves for the portfolio weight vector that maximizes `risk_tolerance · μ'w - (1 - risk_tolerance) · w'Σw` subject to constraints.

**Why it exists**: Turns the expected return vector and covariance matrix into an actual actionable allocation.

**Key functions**:

- `constrained_mvo(mu, cov, tickers, asset_classes, constraints, risk_tolerance, ...) → dict[ticker, weight]`:
  - Formulates as a CVXPY problem: maximize `rt · (μ'w) - (1-rt) · quad_form(w, Σ)`
  - Constraints: weights sum to 1, all ≥ 0 (long-only), each ≤ 25% (concentration cap), plus per-asset-class min/max bounds
  - Tries solvers in order: CLARABEL → OSQP → SCS. This fallback chain handles numerical edge cases — CLARABEL is the most robust for QPs, OSQP is fast but can fail on ill-conditioned problems, SCS is a last resort.
  - Post-solve: clips to [0, 1], renormalizes to sum to 1

- `efficient_frontier(mu, cov, tickers, asset_classes, constraints, n_points, rf) → list[FrontierPoint]`: Runs `constrained_mvo` 50 times across `risk_tolerance ∈ [0, 1]`. Each point includes the weight map, so the frontend can show what the portfolio would look like at each risk level.

- `_build_class_constraints(weights, asset_classes, constraints) → list`: Maps schema names (`stocks`, `bonds`) to internal names (`stock`, `bond`) and builds CVXPY sum constraints for each class.

**Tricky part**: The `max_single_asset_weight = 0.25` default prevents the optimizer from putting everything into one asset (which MVO loves to do when one asset dominates on expected return). But when there's only 1 asset in the portfolio, this cap is relaxed to 1.0.

---

### 6. Regime Detection (`quant/regime.py`)

**What it does**: Classifies the current market environment as bull (0), sideways (1), or bear (2) using three combined signals.

**Why it exists**: Markets behave differently in different regimes. Covariance, expected returns, and risk all need regime-aware adjustments.

**Key class: `RegimeDetector`**

- `fit(market_returns: Series) → self`: Trains on SPY returns. Tries to import `hmmlearn` for Gaussian HMM (captures temporal dependencies — today's regime depends on yesterday's). Falls back to `sklearn.GaussianMixture` (no temporal dependency, just clustering). Sorts states by mean return (highest mean = bull = state 0). Stores rolling 21-day vol history for volatility regime detection.

- `detect_regime(recent_returns: Series) → RegimeState`: The main detection method. Combines three signals:
  1. **HMM/GMM state** (50% weight): Predicts the hidden state from recent returns, gets probability distribution
  2. **Volatility regime** (30% weight): Compares current 21-day rolling vol against historical 25th/75th percentiles. Low vol → bull signal, high vol → bear signal.
  3. **Trend score** (20% weight): If 21-day and 63-day return means are both positive, scores as bullish. Both negative → bearish. Mixed → sideways.
  
  The signals are combined into a 3-element score vector, and the state with the highest combined score wins.

- `RegimeState` dataclass: Not just a label — it carries propagated parameters consumed by other modules: `cov_diag_scale`, `cov_offdiag_scale`, `risk_aversion_mult`, `drift_confidence`, `shrinkage_strength`. This means regime detection directly parameterizes the entire downstream pipeline.

**Non-obvious choice**: Using SPY as the market proxy for regime detection even when the user holds Indian equities. The reasoning: global risk regimes (2008, 2020 COVID, 2022 rate hikes) propagate across markets, and SPY has the most liquid/consistent history. The regime detector is fitted once on startup and refitted weekly.

**Tricky part**: The `_state_order` mapping. HMM states are arbitrary (state 0 might be bull or bear depending on training). After fitting, the code sorts states by their mean return (from `self.model.means_`) and maps them to semantic labels. The `predict()` method remaps raw states through this order.

---

### 7. Monte Carlo Simulation (`quant/monte_carlo.py`)

**What it does**: Simulates 1,000 (configurable) future portfolio value paths using correlated geometric Brownian motion with regime-dependent drift, Student-t innovations, and jump diffusion.

**Why it exists**: Point estimates of future returns are misleading. Monte Carlo gives a distribution of outcomes — median, percentile bands, and probability of loss.

**Key function: `simulate_portfolio(...) → dict`**

The simulation loop:

1. Scale covariance by regime volatility multiplier (bear: ×1.2², bull: ×0.95²)
2. Cholesky decompose `cov_sim` for correlated draws
3. For each path:
   a. Draw Student-t(df=5) innovations, scaled to unit variance: `z = t_raw × √((df-2)/df)`. The `(df-2)/df` scaling ensures `Var(z) = 1`, so the Itô correction below uses the correct variance.
   b. Compute correlated portfolio log-returns: `r = port_drift + z @ chol_row`
   c. Apply jump diffusion (Merton model): Poisson arrivals (λ=2% per day × regime multiplier), jump size ~N(-3%, 4%). Bear regime gets 1.8× the jump intensity.
   d. Compound: `values = V₀ × exp(cumsum(r))`

**Critical Itô correction** (lines 128-132): `drift = mu_arith - 0.5 × σ²_sim`. This converts arithmetic expected return to log-drift for GBM. The `σ²_sim` uses the *simulation* covariance (after regime scaling), not the raw covariance. Getting this wrong was a historically significant bug — if you use raw covariance for the correction but simulate with scaled covariance, drift is wrong.

**Reproducibility**: Uses a deterministic seed derived from SHA-256 of inputs (weights, mu, cov, initial value, paths, horizon). Same inputs always produce the same paths.

**Non-obvious choice**: Student-t with df=5 over Gaussian. Financial returns have fat tails — extreme daily moves happen more often than a Gaussian predicts. df=5 gives a kurtosis of 9 (vs 3 for Gaussian), better capturing tail risk. The scaling factor `√(3/5)` ensures the draws have unit variance despite the heavier tails.

---

### 8. Return Forecaster (`quant/forecaster.py`)

**What it does**: Wraps two ML models (momentum + LSTM) behind a single prediction interface, with clipping and blending.

**Two backends**:

1. **Momentum model** (sklearn, `.pkl`): Loaded from `backend/models/momentum_model.pkl`. Builds 6 features from weekly return series (mean/std over 4/8 weeks, positive weeks count, max drop), predicts weekly return, annualizes by ×52. This is the model that actually loads successfully on startup since the `.pkl` file exists.

2. **LSTM model** (PyTorch): Loaded from `ml/weights/lstm_latest.pt`. Takes 60-day OHLCV window, z-score normalizes, feeds through 2-layer LSTM (128 hidden, dropout 0.2), outputs 30-day return forecast. Averages the 30-day predictions and annualizes by ×252.

**Loading priority**: `_resolve_model_path()` searches for `.pkl` first (in `models/`, `ml/`, and even a sibling `Stock_agent/` directory). If found, uses momentum. Only falls back to LSTM if no `.pkl` exists.

**Key method: `predict_blended(price_df, asset_class, ml_weight=0.30) → float`**:
```
final = 0.30 × ml_prediction + 0.70 × (0.50 × historical + 0.50 × prior)
```
This prevents the ML model from single-handedly driving the BL views. The ML prediction is already clipped to asset-class bounds (e.g., crypto: [-20%, +25%], bonds: [-5%, +10%]).

**How it connects to optimization**: In `optimization_service.py`, if `use_lstm_forecasts` is true, the service calls `predict_blended()` for each ticker. The results become the `ml_forecasts` input to `blend_expected_returns()`, which gives them 15-25% weight depending on regime.

---

### 9. Risk Engine (`quant/risk_engine.py`)

**What it does**: Computes standard portfolio quality and risk metrics from daily log returns.

**Key functions** (all expect daily log returns as input):

- `historical_var(returns, confidence=0.95) → float`: Takes the `(1-c)` percentile of the return distribution. For 95% VaR with 252 observations, this is the ~13th worst daily return. Returned as a positive number (loss magnitude).

- `historical_cvar(returns, confidence=0.95) → float`: Averages all returns beyond the VaR threshold. This is the "expected shortfall" — the average loss given that you're already in the tail.

- `max_drawdown(returns) → float`: Computes cumulative product, tracks running max, returns the worst peak-to-trough drop as a negative fraction.

- `sharpe_ratio(returns, rf) → float`: Uses `_annualised_arithmetic_return()` (which applies Jensen's correction: `μ_log×252 + 0.5×var×252`) for the numerator. Without Jensen's correction, Sharpe ratios computed from log returns are systematically understated.

- `sortino_ratio(returns, rf) → float`: Like Sharpe but uses downside deviation only (returns below the daily risk-free rate). Penalizes downside volatility but not upside volatility.

- `beta(portfolio_returns, market_returns) → float`: `cov(p, m) / var(m)`. Uses SPY as the market benchmark.

**Non-obvious choice**: The risk service (`risk_service.py`) multiplies VaR/CVaR by `total_value_inr` to express them in rupee terms rather than as percentages. This is a UX decision — users understand "₹50,000 at risk" better than "2.3% daily VaR".

---

### 10. Fama-French 5-Factor Model (`quant/factor_model.py`)

**What it does**: Runs OLS regression of portfolio excess returns on the five Fama-French factors to decompose performance attribution.

**The regression**: `R_p - R_f = α + β₁(Mkt-RF) + β₂(SMB) + β₃(HML) + β₄(RMW) + β₅(CMA) + ε`

**Key function: `fama_french_regression(portfolio_returns, ff5_factors, portfolio_id) → FactorExposure`**:
- Aligns portfolio returns with factor data on date
- Computes excess returns (portfolio return minus risk-free rate from FF data)
- Runs `sm.OLS().fit()` with intercept
- Alpha is annualized (×252), residual std is annualized (×√252)

**How factor data is fetched**: `DataFetcher.get_fama_french_factors()` downloads the daily CSV from Ken French's website (Dartmouth), parses it from a ZIP file, converts percentages to decimals. Cached for 24 hours.

**What the output tells you**: β_market near 1.0 means market-driven. Positive β_SMB means small-cap tilt. Positive β_HML means value tilt. Alpha > 0 means returns not explained by the five factors. R² tells you how much of variance is explained by these factors.

---

### 11. Data Fetcher (`quant/data_fetcher.py`)

**What it does**: Single entry point for all external market data. Handles Yahoo Finance, CoinGecko, AMFI mutual fund NAV, NSE live quotes, FX rates, and Ken French factors.

**Design decision**: One class, not separate adapters per source. The reasoning: every caller just needs `get_price_history(ticker, source, days)` — they shouldn't know or care about the source-specific API quirks. The `source` parameter dispatches internally.

**Key methods**:

- `get_price_history(ticker, source, days) → DataFrame`: Cache-first. If cache miss, dispatches to `_fetch_yahoo()`, `_fetch_coingecko()`, or `_fetch_amfi_nav()`. CoinGecko failures fall back to Yahoo crypto tickers (`BTC-USD`, `ETH-USD`).

- `get_latest_prices_in_inr(instruments) → dict[ticker, float]`: Batch-fetches live prices. Yahoo instruments are batched into groups of 50 using the v7 quote API (one HTTP call per 50 tickers). Non-Yahoo instruments fall back to individual `get_latest_price_in_inr()` calls. NSE stocks get a direct quote from `nseindia.com/api/quote-equity`.

- `get_usd_inr_rate() → float`: Cached for 1 hour. Tries Yahoo (`INR=X` ticker) first, falls back to Open Exchange Rates API.

**Reliability**: All HTTP calls go through `_get_json()` / `_get_text()` which are decorated with `@retry(stop=3, wait=exponential(min=2, max=10))` from tenacity. The httpx client has a 30-second timeout and browser-like User-Agent headers (required for Yahoo and NSE).

**Tricky part**: Yahoo Finance's v8 chart API returns OHLCV with timestamps, adjusted close, and sometimes null values in the middle of the series. The fetcher fills null open/high/low with close, null volume with 0, and drops rows where close is null.

---

### 12. Redis Cache (`cache/redis_cache.py`)

**What it does**: Provides get/set/delete/invalidate_pattern operations with automatic fallback to an in-memory dict when Redis is unavailable.

**Why the fallback**: During local development, requiring Redis running is friction. The memory fallback uses a dict of `_MemoryValue` dataclasses with TTL checked on every `get()`. This means the app works identically whether Redis is up or not — just without persistence across restarts.

**`invalidate_pattern(pattern)`**: On Redis, uses `KEYS pattern` then `DELETE`. On memory, strips the trailing `*` and does a prefix match. This is used by the hourly cache refresh job to clear all `prices:*` and `fx:*` keys.

---

### 13. Authentication System

**Backend** (`services/auth_service.py`, `routers/auth.py`, `dependencies.py`):

- Passwords hashed with bcrypt via Passlib
- JWT tokens encoded with HS256 via python-jose, containing `{sub: user_id, exp: timestamp}`
- Token delivered as an HttpOnly cookie (`qp_access_token`) — not in the response body (except implicitly via `Set-Cookie`)
- `get_current_user()` dependency: checks cookie first, falls back to Bearer token (for API testing). Decodes JWT, fetches user from DB, returns `CurrentUser` dataclass.
- Cookie settings are configurable: `SameSite`, `Secure`, path, max-age — all from `config.py`

**Frontend** (`api/client.js`, `components/layout/RequireAuth.jsx`):
- Axios configured with `withCredentials: true` so cookies are sent automatically
- Global 401 interceptor redirects to `/login` (except on auth form requests themselves)
- No token stored in localStorage — pure cookie-based auth

**Non-obvious choice**: Cookie-based auth over localStorage+Bearer. Cookies with `HttpOnly` are immune to XSS token theft. The tradeoff is CSRF vulnerability, but with `SameSite=lax` and no state-changing GET endpoints, this is mitigated.

---

### 14. Portfolio Service (`services/portfolio_service.py`)

**Key function: `_upsert_holdings(portfolio_id, payloads, db) → list[HoldingOut]`**:

This is the most complex DB operation. When adding holdings:
1. Normalizes multiple payloads per ticker into one bucket (aggregating quantity and cost)
2. Validates all tickers exist in the asset table
3. Checks for existing holdings with the same ticker in the portfolio
4. If existing: computes weighted-average buy price across old + new quantities, updates in place
5. If new: inserts
6. Enforces same-currency constraint per ticker (can't add USD and INR positions for the same ticker)

**Why upsert over simple insert**: Users often add to an existing position. Without upsert, they'd have duplicate rows for the same ticker, and every downstream computation that groups by ticker would need deduplication logic.

**`_merge_holdings_rows(rows) → list[dict]`**: Applied when *reading* holdings. If the DB somehow has multiple rows for the same ticker (legacy data, migration artifact), this merges them by weighted average on the fly. Uses a `_cost_basis` tracking field that gets stripped before output.

---

### 15. Optimization Service (`services/optimization_service.py`)

**What it does**: Orchestrates the entire optimization pipeline, connecting portfolio data, market data, regime detection, expected returns, covariance, BL, and MVO.

**The pipeline in `run_optimization()`** (300 lines, the largest single function):

1. Load portfolio snapshot (holdings + asset metadata)
2. Fetch price history for all tickers concurrently (`asyncio.gather` with `return_exceptions=True`)
3. Filter out failed fetches (graceful degradation)
4. Align returns + FX normalization
5. Detect regime (if enabled and detector is fitted)
6. Compute covariance: Ledoit-Wolf → volatility shrinkage → regime scaling
7. Compute blended expected returns (equilibrium + historical + ML + momentum)
8. If user views exist: run Black-Litterman to blend views, compute posterior covariance
9. Run constrained MVO with the selected risk tolerance
10. Generate efficient frontier (50 points)
11. Fetch live INR prices for current value calculation
12. Compute rebalance trades (target value - current value per ticker)
13. Return the full `OptimizationResult` DTO

**`init_ml_models(regime_detector, forecaster)`**: Called once at startup from `main.py`. Stores the detector and forecaster as module-level globals. Also shares the regime detector with `risk_service` via `set_regime_detector()`.

**Background re-optimization**: When a holding is added or deleted, the portfolio router fires `_reoptimize_portfolio_after_change()` as a `BackgroundTasks` task. This waits 2 seconds (debounce), runs optimization at `risk_tolerance=0.5`, stores the recommended asset-class weights in `portfolios.last_optimized_weights`, and inserts a drift alert if the actual allocation diverges from the recommended by >5%.

---

### 16. Onboarding System

**Backend** (`services/onboarding_service.py`, `services/portfolio_builder.py`):

- `compute_risk_score(payload) → int [1-10]`: Starts from a base score matrix (3 risk appetites × 3 horizons), then adjusts: young investors +2, old investors -2, variable income -1, no existing investments -1. Final score is ceil(raw/2), clamped to [1, 10].

- `recommend_portfolio(user_id, db)`: Fetches the user's profile, computes risk-adjusted constraints (conservative/moderate/aggressive tiers), creates or updates the user's portfolio with those constraints, then builds a recommended allocation using `build_recommended_portfolio()`.

- `build_recommended_portfolio(risk_score, investment_amount) → list[dict]`: Three static allocation templates based on risk score (1-3, 4-6, 7-10). Conservative: 45% bonds, 20% ETF, 15% gold, 10% stocks, 2% crypto. Aggressive: 15% bonds, 15% ETF, 10% gold, 45% stocks, 15% crypto. Returns ticker, class, weight, and INR amount.

- `_get_reference_prices()`: Fetches live INR prices for all recommended tickers so the onboarding UI can show current prices alongside recommendations.

**Frontend** (`pages/Onboarding.tsx`): A 6-step wizard (investment amount → horizon → risk appetite → income stability → existing investments → age group) followed by profile submission, portfolio recommendation display, optional bulk holding addition, and completion.

---

### 17. Portfolio Monitoring (`services/portfolio_monitor.py`)

**What it does**: Checks all active portfolios for allocation drift and peak drawdown, generates alerts.

**Key functions**:

- `monitor_portfolio(portfolio_id, db, fetcher) → RebalanceAlert | None`: Fetches current live values for all holdings, computes current asset-class weights, compares against `last_optimized_weights` stored on the portfolio. If any class drifts >5%, flags those assets. Also tracks peak value — if current value drops >10% from peak, generates a drawdown alert.

- `monitor_all_active_portfolios(db, fetcher, persist_alerts)`: Iterates all portfolios belonging to active users. Called by two scheduler jobs: every 30 min during market hours (9-15 IST, M-F) without persisting, and once at 15:45 IST (EOD) with persistence.

**Non-obvious choice**: Market-hours monitoring doesn't persist alerts (just logs them) to avoid spamming users during intra-day volatility. Only the EOD check persists alerts to the database. This is encoded in the scheduler: `persist_alerts=False` for market hours, `persist_alerts=True` for EOD.

---

### 18. Scheduled Jobs (`tasks/scheduler.py`)

Five cron jobs on the AsyncIO scheduler:

| Job | Schedule | What it does |
|---|---|---|
| `refresh_price_cache` | Every hour | Invalidates all `prices:*` and `fx:*` cache keys |
| `refit_regime_detector` | Sunday 02:00 IST | Refetches 3 years of SPY, refits the HMM |
| `trigger_lstm_retrain` | 1st of month, 03:00 IST | Logs a reminder — does NOT actually retrain |
| `portfolio_monitor_market_hours` | Mon-Fri, every 30 min 09:00-15:00 IST | Runs drift/drawdown checks, logs only |
| `portfolio_monitor_eod` | Mon-Fri 15:45 IST | Runs drift/drawdown checks, persists alerts |

---

### 19. Database Layer

**Engine setup** (`database.py`): Async SQLAlchemy with `asyncpg` driver. Connection pool: 10 base + 20 overflow. `pool_pre_ping=True` to detect stale connections. `statement_cache_size=0` to avoid asyncpg prepared statement issues with connection pooling.

**SQLite fallback**: If the primary Postgres connection fails in the lifespan handler, `configure_database()` swaps the global engine and session maker to `aiosqlite`. The SQLite file is at the project root (`quantportfolio.db` — present in the repo).

**Tables** (5 + 1):
- `users`: id (UUID), email (unique, indexed), hashed_password, full_name, is_active, timestamps
- `assets`: ticker (PK, string), name, asset_class (enum), exchange, currency, data_source, is_active
- `portfolios`: id (UUID), user_id (FK→users, cascade delete), name, description, base_currency, constraints (JSON), last_optimized_weights (JSON), peak_value (Float), timestamps
- `holdings`: id (UUID), portfolio_id (FK→portfolios, cascade delete), ticker (FK→assets), quantity, avg_buy_price, buy_currency, timestamps
- `investor_profiles`: id (UUID), user_id (FK→users, unique, cascade delete), investment_amount, investment_horizon, risk_appetite, income_stability, existing_investments, age_group, risk_score, timestamps
- `portfolio_alerts`: id (UUID), portfolio_id (FK→portfolios, cascade delete), alert_type, message, created_at, is_read

**Migrations**: 4 Alembic versions — initial schema (April 2026), investor profiles, portfolio monitoring columns (peak_value, last_optimized_weights), alerts table.

---

### 20. Frontend Architecture

**Routing** (`App.tsx`):
- `/login`, `/register`: Public pages
- `/onboarding`: Requires auth but not onboarding completion
- `/`, `/dashboard`, `/optimize`, `/risk`, `/analytics`, `/holdings`: Require auth + onboarding
- `RequireAuth`: Checks cookie existence via `/api/v1/auth/me` call
- `RequireOnboarding`: Checks `qp_onboarded` flag in Zustand store (persisted to localStorage)

**State management**:
- `portfolioStore` (Zustand): Holds `portfolioId`, `portfolioName`, `regime`, `onboarded`. Persists onboarding flag to localStorage. Reset on logout.
- React Query (`@tanstack/react-query`): Used by `useRisk`, `useAnalytics`, `useAuth`, `useAlerts`, `useOptimize` hooks for server state. Configured with stale times (30s-5min) and refetch intervals.

**Data flow for the Dashboard page**: `useAnalytics(portfolioId)` calls `GET /api/v1/analytics/{id}`, which returns total value, PnL, allocation breakdown, performance series, benchmark comparisons, holdings breakdown with sparklines, and factor exposure — all in one response. The `portfolioMappers.js` reshapes this into chart-ready formats.

**Pages**:
- `Dashboard.jsx` (11KB): Summary cards (value, PnL, day change), allocation pie, performance line chart with SPY benchmark, risk snapshot, top holdings table
- `Holdings.jsx` (5KB): Asset search, add holding form, holdings table with sparklines, delete
- `Optimize.jsx` (7KB): Risk tolerance slider, asset-class constraint controls, user view inputs, LSTM/regime toggles, efficient frontier chart, optimal vs current weight comparison, rebalance trades
- `Risk.jsx` (8KB): VaR/CVaR cards, Monte Carlo fan chart, correlation matrix heatmap, Sharpe/Sortino/Calmar/Beta gauges
- `Analytics.jsx` (7KB): Factor exposure radar/bar chart, return attribution, risk attribution, per-holding PnL table
- `Onboarding.tsx` (32KB): Multi-step wizard with animated transitions

---

### 21. End-to-End Request Trace: "Run Optimization"

1. User adjusts risk tolerance slider to 0.7, clicks "Optimize" on the frontend
2. `useOptimize` hook (React Query mutation) calls `runOptimization()` API wrapper
3. `POST /api/v1/optimize/` with `{portfolio_id, risk_tolerance: 0.7, use_regime_scaling: true, ...}`
4. `@limiter.limit("5/minute")` checks rate — passes if under 5 calls/min from this IP
5. `get_current_user` dependency: reads `qp_access_token` cookie → decodes JWT → fetches user from DB
6. `run_optimization()` in optimization_service:
   - `load_portfolio_snapshot()`: 3 DB queries (portfolio, holdings, assets)
   - `asyncio.gather()`: Fetches 282 days of price history per ticker concurrently (Redis cache hit or Yahoo/CoinGecko)
   - `align_returns()`: INR prices ÷ USD/INR rate, log returns, inner join on date
   - `RegimeDetector.detect_regime()`: HMM predicts from first ticker's return series → "bull" with 72% confidence
   - `compute_covariance()`: Ledoit-Wolf on 252-day window → annualize × 252
   - `shrink_volatility()`: Crypto vol pulled from 85% → 67% (α=0.45 blend with 55% target)
   - `scale_covariance_by_regime()`: Bull → diagonal ×0.85, off-diagonal ×0.80
   - `blend_expected_returns()`: Bull profile → eq 30%, hist 30%, ML 25%, views 15%
   - `constrained_mvo()`: CLARABEL solves in ~10ms → weight map
   - `efficient_frontier()`: 50 solves → frontier points
   - `get_latest_prices_in_inr()`: Batch Yahoo quote for current values
   - Assembles `OptimizationResult` with regime, Sharpe, weights, frontier, trades
7. FastAPI serializes via Pydantic → JSON response
8. Frontend `onSuccess`: stores regime in Zustand, maps result via `mapOptimizationResult()` → renders frontier chart, weight bars, trade table

---

### 22. Local Development Setup

#### Prerequisites
- Python 3.12+, Node.js 18+
- PostgreSQL (or let SQLite fallback handle it)
- Redis (or let in-memory fallback handle it)

#### Backend
```bash
cd backend
pip install -r requirements.txt
# Also needed but not in requirements.txt:
pip install python-dotenv psycopg2-binary
# Copy .env.example → .env, fill in SECRET_KEY and DATABASE_URL
alembic upgrade head  # or skip — tables auto-create on startup
uvicorn main:app --reload --port 8000
```

#### Frontend
```bash
cd frontend
npm install
npm run dev  # → http://localhost:5173
```

#### Docker (full stack)
```bash
docker compose up --build
# → Frontend on :8081, Backend on :8000, Postgres on :5432, Redis on :6379
```

#### First-run flow
1. Register at `/register`
2. Complete onboarding wizard (6 steps)
3. Recommended holdings are offered — optionally add them
4. Navigate to Dashboard, Holdings, Optimize, Risk, Analytics

---

### 23. Testing

#### Backend tests (16 files)
```bash
pytest backend/tests
```

Coverage includes: Black-Litterman math, constrained MVO bounds, VaR/CVaR calculations, Monte Carlo output shape, Fama-French regression, asset router CRUD, onboarding flow, portfolio monitor drift detection, holding upsert logic, data fetcher mocking, forecaster predictions, optimization duplicate handling, API integration tests.

#### Frontend tests
```bash
cd frontend
npm run test
```
Coverage is minimal: `portfolioMappers.test.ts` tests the data reshaping functions. No page or component tests.

---

### 24. Practical Caveats

- **FX is a snapshot, not a time series**: All cross-currency calculations use a single `usd_inr_rate` fetched once per request, not a daily historical series. This means FX volatility is not captured in the return matrix.
- **Regime proxy**: The HMM is trained on SPY regardless of the user's portfolio composition. This works for global risk regime detection but may not capture India-specific regime shifts.
- **LSTM training is offline**: The monthly scheduler job only logs a reminder. Actual retraining requires running `python backend/ml/trainer.py` manually.
- **CORS origins are in settings**: The old README noted they were hardcoded — this has since been fixed. `ALLOWED_ORIGINS` in `config.py` is used by the CORS middleware and supports env-var override.
- **base_currency field**: Exists on portfolios (INR or USD) but all analytics are computed in USD internally and converted to INR for display. The field doesn't change computation behavior.
- **React Query vs manual hooks**: Risk, analytics, auth, alerts, and optimization use React Query. Portfolio and holdings use manual `useState`/`useEffect`. Both work; they're just inconsistent.
- **No WebSocket/SSE**: All data is fetched via polling. React Query handles refetch intervals (30s-60s for analytics/risk).
