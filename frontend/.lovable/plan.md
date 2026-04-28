# QuantPortfolio — Frontend Build Plan

A quant portfolio management dashboard with a Bloomberg-meets-Swiss-design aesthetic. Five pages, dense typography, mock data throughout, ready to wire to a backend later.

## Look & Feel

- Pure white background with a subtle dot-grid pattern
- Floating cards with layered soft shadows
- DM Sans for UI, JetBrains Mono for all numbers/tickers
- Blue (#2563EB) used sparingly — only where action lives
- Green/red for P&L, colored regime badge in navbar

## Pages

**1. Dashboard** — Overview
- 4 stat cards: Total Value, Daily P&L, Sharpe, Volatility
- Performance chart (portfolio vs benchmark) with 7D/1M/3M/1Y selector
- Allocation donut by asset class
- Holdings table preview

**2. Optimize** — Black-Litterman + MVO
- Left config panel: risk tolerance slider, asset-class bound sliders (min/max per class), user views panel, LSTM/regime toggles, Run button
- Right: efficient frontier scatter with optimal point highlighted
- Below: optimal weights bar chart + rebalancing trades list
- Infeasibility warning when sum of minimums > 100%

**3. Risk** — VaR, CVaR, Monte Carlo
- 4 risk stat cards (VaR, CVaR, Max Drawdown, Sharpe) with colored left stripes
- Monte Carlo simulation chart with percentile bands (p5/p25/p50/p75/p95) and horizon selector
- Correlation matrix (Tailwind grid, color-scaled)
- Secondary metrics row: Sortino, Calmar, Beta, Ann. Return, Ann. Vol

**4. Analytics** — Factor decomposition
- Full-width Fama-French 5-factor exposure bar chart with R²
- Return Attribution list (holdings ranked by contribution)
- Risk Attribution list (holdings ranked by risk %)

**5. Holdings** — Full table
- Toolbar: search input, asset-class filter pills, Add Holding button
- Full table: Ticker, Class, Qty, Avg Buy, Current, Value, P&L, P&L%, Weight bar
- Right-side slide-in drawer for adding holdings

## Shared Components

- `Navbar` with logo, nav links, regime badge (bull/sideways/bear), user avatar
- `PageWrapper` with title/subtitle
- `Card`, `StatCard`, `Badge`, `Button`, `Toggle`, `Slider`, `RangeSlider`
- Charts: PerformanceChart, AllocationDonut, FrontierScatter, MonteCarloChart, CorrelationMatrix, FactorBar, WeightsBar (all Recharts except correlation matrix)
- Domain: HoldingsTable, ConstraintSliders, UserViewsPanel, RebalanceTrades, AddHoldingDrawer

## State & Data

- Zustand store for auth token, selected portfolio ID, current market regime
- Axios client with bearer-token interceptor, base URL from `VITE_API_URL`
- Hooks: `usePortfolio`, `useOptimize`, `useRisk`, `useAnalytics` — all follow `{ data, loading, error, refetch }` shape
- All pages ship with realistic mock data so the UI is fully interactive before the backend exists

## Animations

- Cards stagger-fade in on page load (`animate-fadeUp` with delay)
- P&L values flash blue for 300ms on update
- Drawer slides in from right
- Subtle hover lift on cards

## Technical Details

- React 18 + Vite, JSX throughout (no `.tsx`)
- Tailwind CSS with extended config: DM Sans + JetBrains Mono fonts, custom blue palette, card shadow tokens, fadeUp keyframes
- React Router v6 with `React.lazy` + `Suspense` per page for code splitting
- Radix UI primitives for sliders, toggles, tooltips
- Recharts for all charts except the correlation matrix (pure Tailwind grid for cell-level control)
- Dot-grid background via a 3-line raw CSS rule in `index.css`
- Google Fonts loaded in `index.html`
- Existing placeholder `Index.tsx` replaced; `/` redirects to `/dashboard`
- Shadcn UI components already in the project will be kept available but the spec's custom `components/ui/*` set will be built fresh to match the exact design language

## Out of Scope (for this first pass)

- Real authentication flow (login/signup screens) — store accepts tokens but no UI yet
- Backend integration — hooks are stubbed with mock data, ready to swap to live API
- Chart export, PDF reports, portfolio CRUD beyond the Add Holding drawer shell
