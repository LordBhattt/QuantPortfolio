# QuantPortfolio Audit: Known Issues

Audit date: 2026-11-13. This was an audit-only run. Application code, configuration,
and the seeded repository database were not changed. Mutating API/UI flows were run
against a temporary copy of the SQLite database and that copy was removed afterward.

## 1. Summary

| Classification | Count | Meaning |
|---|---:|---|
| Passing | 16 | Verified with a command, response, or browser observation |
| Broken | 5 | Fails, blocks a requested flow, or violates a stated demo requirement |
| Risky | 10 | Works, but is slow, misleading, insecure by default, stale, or fragile |

The most serious demo risks are the 10--26 second live-data requests and
environment-specific setup requirements.

Current status after the follow-up fixes: onboarding, backtest admission,
proxy labels, unused mock fixtures, responsive overflow, and empty-account
benchmark requests are fixed. The intentionally skipped items are marked
below as known, not fixing.

## 2. BLOCKERS

### B1. New-user onboarding can be skipped and cannot be reopened (FIXED)

- **Where:** `frontend/src/store/portfolioStore.js`, `frontend/src/App.tsx`,
  `frontend/src/pages/Register.jsx`.
- **Evidence:** In a clean browser context, registering
  `ui_audit_<timestamp>@example.com` returned to `/dashboard`, which displayed
  `Select Portfolio`, `No holdings yet`, and `₹0`. Navigating directly to
  `/onboarding` immediately redirected back to `/dashboard`; the five-step
  onboarding form was not reachable. The same browser had a persisted client
  onboarding state from the preceding login. This leaves a valid new account
  without a portfolio and without an accessible recovery path.
- **Suggested fix:** Derive onboarding completion from the authenticated server
  profile/portfolio state, or clear/namespace the client state on user changes.
- **Estimated effort:** 45--90 minutes.

### B2. Backtest parameter combinations hit a 429 rate limit (FIXED)

- **Where:** `backend/routers/backtest.py:28` (`3/minute`).
- **Evidence:** A valid authenticated sweep of the required 1/3/5-year by
  weekly/monthly/quarterly combinations produced:
  - `1Y weekly`: HTTP 200, 16.42s
  - `1Y monthly`: HTTP 200, 13.45s
  - `1Y quarterly`: HTTP 200, 0.03s (cache)
  - all six 3Y/5Y combinations: HTTP 429, body
    `{"error":"Too many requests","code":"rate_limit_exceeded","detail":"Rate limit exceeded"}`
- **Suggested fix:** Separate expensive backtest admission control from normal
  interactive requests, queue jobs, or provide a user-scoped cache-aware limit
  that permits the documented parameter sweep.
- **Estimated effort:** 60--120 minutes.

### B3. Several core demo requests exceed the 10-second budget (KNOWN, NOT FIXING)

- **Where:** risk, analytics, optimization, and backtest services.
- **Evidence:** Authenticated calls against the seeded demo returned HTTP 200 but
  took: analytics `25.55s`, risk `16.05s`, optimize `17.08s`, backtest
  `12.99s`. Smoke-test timings also recorded custom stress at `10.3s` and
  backtest at `19.7s`. No response contained NaN or Infinity.
- **Suggested fix:** Prewarm/cache histories before the demo, move expensive
  calculations to jobs, and expose progress rather than blocking page loads.
- **Estimated effort:** 2--4 hours.

### B4. A persistent secret is required outside development (FIXED)

- **Where:** `backend/config.py:18`:
  `SECRET_KEY: str = "change-me-to-a-long-random-secret"`.
- **Evidence:** Startup now rejects missing or known placeholder values outside
  development. Local setup generates a random development secret, and the
  generator prints a persistent secret for production configuration.
- **Suggested fix:** Keep `SECRET_KEY` out of source control and configure it
  through the deployment environment.
- **Estimated effort:** Complete.

### B5. The ordinary backend test command is host-permission fragile (KNOWN, NOT FIXING)

- **Where:** `backend/tests/conftest.py:35` and pytest cache/temp handling.
- **Evidence:** The requested `pytest backend/tests -q` produced `46 passed, 10
  errors`; every error was setup failure
  `PermissionError: [WinError 5] Access is denied:
  C:\Users\ADMIN\AppData\Local\Temp\pytest-of-ADMIN`. Rerunning with an isolated
  `--basetemp` produced `56 passed` but still emitted three pytest cache
  permission warnings for `.pytest_cache`.
- **Suggested fix:** Make the test setup choose a writable project-local temp
  directory or document the required Windows temp permissions.
- **Estimated effort:** 20--45 minutes.

## 3. MAJOR (wrong or misleading output)

### M1. Proxy usage is only partially disclosed in the UI (FIXED)

- **Where:** `backend/services/stress_service.py`, `frontend/src/pages/Risk.jsx:260`.
- **Evidence:** The stress API returned `is_proxy: true` and proxy tickers such as
  `SPY` for `RELIANCE.NS`, `NIFTYBEES.NS`, `HDFCBANK.NS`, and `TCS.NS`, and
  `AGG` for `LTGILTDIR.NS`. The UI displays only the generic note
  `Some holdings use proxy data (asset had no history in this window)`, not the
  proxy ticker beside each holding.
- **Suggested fix:** Display the exact proxy ticker and source on each affected
  holding.
- **Estimated effort:** 30--60 minutes.

### M2. A fresh clone contains generated market-data cache files (KNOWN, NOT FIXING)

- **Where:** `backend/data/cache/*.parquet`.
- **Evidence:** `git ls-files` reported 24 tracked parquet files. They are dated
  `2026-11-13`, contain snapshots through `2026-11-11`/`2026-11-12`, and are
  generated market data rather than source. A fresh clone reproduced all 24 files.
- **Suggested fix:** Ignore generated caches and populate them during setup or
  explicitly publish a versioned data snapshot with its provenance.
- **Estimated effort:** 15--30 minutes, plus a repository cleanup decision.

### M3. The repository retains unused hardcoded mock portfolio data (FIXED)

- **Where:** `frontend/src/lib/mockData.js`.
- **Evidence:** The file contains hardcoded holdings, INR prices, performance
  curves, weights, Monte Carlo paths, factors, and `Math.random()` frontier
  points. A repository-wide import search found no importer; `Tech-ReadMe.md:82`
  acknowledges it as a test/dev artifact. This contradicts the demo claim in
  `docs/DEMO.md:153` that there are no hardcoded demo values anywhere.
- **Suggested fix:** Remove the unused artifact or label it clearly as excluded
  development data and change the documentation claim.
- **Estimated effort:** 15--30 minutes.

### M4. Mobile/small-laptop layout overflows horizontally (FIXED)

- **Where:** frontend shell/dashboard layout.
- **Evidence:** Browser audit at viewport `800x600` measured
  `document.documentElement.scrollWidth = 928`, so `scrollWidth > innerWidth`.
  The dashboard still rendered, but the page required horizontal scrolling.
  At laptop width `1366x768`, all six authenticated pages rendered charts or
  explicit empty states without NaN/undefined/Infinity text or page errors.
- **Suggested fix:** Add responsive breakpoints and constrain wide tables/charts
  to the viewport.
- **Estimated effort:** 45--90 minutes.

### M5. New empty accounts show an unhelpful benchmark failure (FIXED)

- **Where:** Dashboard empty state.
- **Evidence:** Immediately after the UI registration flow, the dashboard showed
  the correct empty portfolio state (`₹0`, `No holdings yet`) but also
  `Benchmark data unavailable` while the backend was healthy. This is not a
  crash, but it looks like a service failure before the user has any portfolio
  data.
- **Suggested fix:** Suppress benchmark/factor calls until a portfolio has
  holdings, or explain that benchmark data is unavailable for an empty account.
- **Estimated effort:** 20--40 minutes.

## 4. MINOR (cosmetic, docs, cleanup)

- ESLint exits 0 but reports 8 warnings: seven React fast-refresh export
  warnings and one missing `useEffect` dependency in
  `frontend/src/pages/Onboarding.tsx:205`.
- `npm run build` exits 0 but reports stale Browserslist data
  (`caniuse-lite` is 17 months old).
- Pytest emits 12 jose `datetime.utcnow()` deprecation warnings plus the three
  cache-permission warnings noted above.
- Startup logs an `hmmlearn` non-convergence warning:
  `Model is not converging ... Delta is -5.011...`; the app continues and the
  regime API returns data, but this is examiner-visible.
- `README.md:688` says `python-dotenv`, `psycopg2-binary`, and `fakeredis` are
  extra packages not pinned in requirements, but all three are present in
  `backend/requirements.txt`. `Tech-ReadMe.md:612` describes the same setup
  differently.
- `README.md:682` says CORS origins are hardcoded, while
  `backend/config.py:20` and `backend/main.py:100` use configurable
  `ALLOWED_ORIGINS`.
- There is no SMTP email delivery path. Registration, login, and in-app alerts
  work; `docs/DEMO.md:185` documents the limitation.
- A model report-card page is not present; the available pages are Login,
  Register, Onboarding, Dashboard, Holdings, Optimize, Risk, Analytics, and
  Backtest.
- The fresh-clone dry-run used Node `v24.11.0` and Python `3.12.10`; `npm ci
  --ignore-scripts --dry-run` succeeded. The README recommends Node 18+, so
  Node-version compatibility is not demonstrated by the documented baseline.

## 5. Passing checks

- Backend isolated rerun: `56 passed`; no failed assertions.
- Frontend `npm run lint`: exit 0, 0 errors.
- Frontend `npm run build`: exit 0.
- Frontend `npm run test -- --run`: 20 tests passed.
- `backend/scripts/endpoint_smoke_test.py`: 7/7 calls passed, 0 failures, 0
  calls over 30 seconds.
- Every live API response sampled contained neither NaN nor Infinity.
- `/health` returned HTTP 200 and `{"status":"ok","version":"1.0.0"}`.
- Valid authenticated CRUD routes on the isolated SQLite copy returned expected
  200/201/204 statuses, including register, login, profile, recommend, portfolio,
  holdings, assets, alerts, and logout.
- Invalid authenticated inputs returned expected 422/404 responses; unauthenticated
  protected routes returned HTTP 401.
- The no-slash duplicate `/api/v1/backtest` route returned HTTP 200.
- Dashboard totals independently reconciled: weights summed to `1.0`, holding
  values summed to `₹120,146.4429`, and holding P&L summed to `-₹3,853.5575`,
  matching analytics totals.
- Independent recomputation of backtest final value, profit, CAGR, Sharpe, and
  max drawdown matched the API exactly for Optimized, QP Smart, and Equal Weight.
- Stress results were directionally sensible: GFC `-8.00%` and COVID `-18.77%`,
  with negative INR impacts.
- Dashboard, Holdings, Optimize, Risk, Analytics, and Backtest rendered live
  content/charts at laptop width without visible NaN/undefined/Infinity values.
- Optimize displayed `Using: ML not used`; startup logs reported the GBM model
  disabled because `IC=0.0173, t=0.61` failed its gates.
- Cache behavior worked: a repeated cached backtest returned in approximately
  `0.03s`, versus `12--20s` for uncached runs.
- Relative Markdown links in README, Tech-ReadMe, and `docs/*.md` all resolved.
- `.env`, SQLite databases, and audit temporary directories were untracked and
  removed after the audit.

## 6. Demo risk list

1. **Onboarding skips for a new browser user.** Use a browser profile with
   cleared site storage and verify a portfolio exists before demonstrating
   registration.
2. **Backtest requests can return 429.** Run one pre-warmed cached configuration
   and avoid demonstrating a rapid multi-parameter sweep.
3. **Live data can make pages wait 10--26 seconds.** Preload Dashboard, Risk,
   Analytics, Optimize, and Backtest before the examiner arrives; keep the
   explicit loading/error states visible rather than refreshing repeatedly.
4. **Yahoo/CoinGecko availability changes proxy coverage.** Use the seeded demo
   and explain the visible proxy note; do not imply every holding has native
   historical data.
5. **The default JWT secret and public demo password look like production
   credentials.** Run only locally with a generated `SECRET_KEY`, and do not
   present the development defaults as deployment configuration.
