import { useState, useEffect, useCallback, useRef } from "react";

import MonteCarloChart from "../components/charts/MonteCarloChart";
import CorrelationMatrix from "../components/charts/CorrelationMatrix";
import PageWrapper from "../components/layout/PageWrapper";
import Card from "../components/ui-qp/Card";
import EmptyState from "../components/ui-qp/EmptyState";
import { useMonteCarlo, useRiskMetrics } from "../hooks/useRisk";
import { useHoldings } from "../hooks/usePortfolio";
import { usePortfolioStore } from "../store/portfolioStore";
import { formatINR, formatPct } from "../utils/format";
import { ProbabilityCard } from "../components/dashboard/StatCards";
import { getStressTest, runCustomStress } from "../api/stress";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell } from "recharts";

const HORIZONS = ["3M", "6M", "1Y", "3Y"];
const HORIZON_DAYS = { "3M": 63, "6M": 126, "1Y": 252, "3Y": 756 };
const N_PATHS = 1000;

function SkeletonBlock({ className }) {
  return <div className={`bg-gray-100 animate-pulse rounded-xl ${className}`} />;
}

export default function Risk() {
  const portfolioId = usePortfolioStore((s) => s.portfolioId);
  const [horizon, setHorizon] = useState("1Y");
  const { data: holdings, loading: holdingsLoading } = useHoldings(portfolioId);
  const hasHoldings = Boolean(holdings?.length);

  const { data: risk, loading: riskLoading, error: riskError } = useRiskMetrics(portfolioId, hasHoldings);
  const { data: mc, loading: mcLoading, error: mcError } = useMonteCarlo(portfolioId, N_PATHS, HORIZON_DAYS[horizon], hasHoldings);

  const isLoading = portfolioId && (holdingsLoading || riskLoading || mcLoading);
  const probLoss = (mc?.prob_loss ?? 0) * 100;
  const probProfit = Math.max(0, 100 - probLoss);
  const matrix = risk?.correlation_matrix || {};
  const tickers = Object.keys(matrix);
  const empty = [riskError, mcError].some((value) => value?.toLowerCase().includes("no holdings"));

  const stats = [
    { label: "VaR (95%)", value: risk ? `-${formatINR(risk.var_95)}` : "₹—", sub: "daily loss threshold" },
    { label: "CVaR (95%)", value: risk ? `-${formatINR(risk.cvar_95)}` : "₹—", sub: "expected shortfall" },
    { label: "Max Drawdown", value: risk ? formatPct(risk.max_drawdown) : "—%", sub: "peak to trough" },
    { label: "Sharpe Ratio", value: risk ? Number(risk.sharpe_ratio).toFixed(2) : "—", sub: "risk-adjusted return" },
  ];

  return (
    <PageWrapper title="Risk" subtitle="VaR, CVaR, Monte Carlo simulation">
      {(riskError || mcError) && !empty && !isLoading && (
        <Card className="p-4 mb-6 border border-red-200 bg-red-50">
          <p className="text-sm font-mono text-red-700">{riskError || mcError}</p>
        </Card>
      )}

      {empty && !isLoading ? (
        <Card className="p-6">
          <EmptyState title="No holdings to analyze yet" subtitle="Add holdings to unlock portfolio risk metrics." />
        </Card>
      ) : (
        <>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            {stats.map((stat, index) => (
              <div key={stat.label} className="animate-fadeUp opacity-0" style={{ animationDelay: `${index * 60}ms` }}>
                {isLoading ? (
                  <SkeletonBlock className="h-28 w-full" />
                ) : (
                  <Card className="p-5">
                    <div className="text-[11px] font-sans font-semibold tracking-[0.14em] uppercase text-gray-400">{stat.label}</div>
                    <div className="mt-2 font-mono text-2xl font-bold text-gray-900">{stat.value}</div>
                    <div className="mt-1 text-xs font-mono text-gray-500">{stat.sub}</div>
                  </Card>
                )}
              </div>
            ))}
          </div>

          <div className="animate-fadeUp opacity-0 mb-6" style={{ animationDelay: "240ms" }}>
            <Card className="p-5 min-h-[420px]">
              <div className="flex items-start justify-between mb-4 flex-wrap gap-4">
                <div>
                  <h2 className="text-[15px] font-sans font-semibold text-gray-900">Monte Carlo Simulation</h2>
                  <p className="text-xs font-mono text-gray-500 mt-0.5">{N_PATHS.toLocaleString("en-IN")} correlated paths - INR</p>
                </div>
                <div className="inline-flex items-center border border-black/[0.08] rounded-full p-0.5">
                  {HORIZONS.map((token) => (
                    <button
                      key={token}
                      onClick={() => setHorizon(token)}
                      className={`px-3 py-1 text-[11px] font-mono font-medium rounded-full transition-colors ${
                        horizon === token ? "bg-gray-900 text-white" : "text-gray-500 hover:text-gray-900"
                      }`}
                    >
                      {token}
                    </button>
                  ))}
                </div>
              </div>

              {isLoading ? (
                <SkeletonBlock className="h-[380px] w-full" />
              ) : (
                <MonteCarloChart data={mc?.percentiles || {}} />
              )}

              <div className="mt-6 pt-5 border-t border-black/[0.06]">
                <ProbabilityCard profit={probProfit} loss={probLoss} horizon={horizon} />
              </div>
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
            <div className="lg:col-span-2 animate-fadeUp opacity-0" style={{ animationDelay: "300ms" }}>
              <Card className="p-5 h-full">
                <h2 className="text-[15px] font-sans font-semibold text-gray-900 mb-4">Correlation Matrix</h2>
                {isLoading ? (
                  <SkeletonBlock className="h-[280px] w-full" />
                ) : tickers.length > 0 ? (
                  <CorrelationMatrix tickers={tickers} matrix={matrix} />
                ) : (
                  <EmptyState title="No correlation data yet" subtitle="Correlation will appear once market history is available." />
                )}
              </Card>
            </div>
            <div className="animate-fadeUp opacity-0" style={{ animationDelay: "360ms" }}>
              <Card className="p-5 h-full">
                <h2 className="text-[15px] font-sans font-semibold text-gray-900 mb-4">Supplementary</h2>
                {isLoading ? (
                  <div className="space-y-3">
                    {Array.from({ length: 5 }).map((_, index) => (
                      <SkeletonBlock key={index} className="h-10 w-full" />
                    ))}
                  </div>
                ) : (
                  <div className="space-y-3">
                    {[
                      { label: "Sortino Ratio", value: risk ? Number(risk.sortino_ratio).toFixed(2) : "—" },
                      { label: "Calmar Ratio", value: risk ? Number(risk.calmar_ratio).toFixed(2) : "—" },
                      { label: "Beta", value: risk ? Number(risk.beta).toFixed(2) : "—" },
                      { label: "Ann. Return", value: risk ? formatPct(risk.annualised_return) : "—%" },
                      { label: "Ann. Volatility", value: risk ? formatPct(risk.annualised_volatility) : "—%" },
                    ].map((metric) => (
                      <div key={metric.label} className="flex items-baseline justify-between border-b border-black/[0.04] pb-2 last:border-0">
                        <span className="text-[11px] font-sans font-semibold tracking-[0.14em] uppercase text-gray-400">{metric.label}</span>
                        <span className="font-mono text-sm text-gray-900">{metric.value}</span>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            </div>
          </div>
        </>
      )}

      {/* Stress Test Section */}
      {portfolioId && hasHoldings && <StressTestSection portfolioId={portfolioId} />}
    </PageWrapper>
  );
}

function StressTestSection({ portfolioId }) {
  const [stressData, setStressData] = useState(null);
  const [stressLoading, setStressLoading] = useState(false);
  const [stressError, setStressError] = useState(null);
  const [activeScenario, setActiveScenario] = useState(0);
  const [shock, setShock] = useState({ equities_pct: 0, crypto_pct: 0, gold_pct: 0, bonds_pct: 0, inr_move_pct: 0 });
  const [customResult, setCustomResult] = useState(null);
  const debounceRef = useRef(null);

  useEffect(() => {
    setStressLoading(true);
    getStressTest(portfolioId)
      .then(setStressData)
      .catch((e) => setStressError(e?.response?.data?.detail || e.message))
      .finally(() => setStressLoading(false));
  }, [portfolioId]);

  const applyCustomShock = useCallback((params) => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      runCustomStress(portfolioId, params)
        .then(setCustomResult)
        .catch(() => {});
    }, 350);
  }, [portfolioId]);

  const handleShockChange = (key, val) => {
    const next = { ...shock, [key]: val };
    setShock(next);
    applyCustomShock(next);
  };

  const scenarios = stressData?.historical_scenarios || [];
  const active = scenarios[activeScenario];
  const fmtINRVal = (v) => new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(Math.abs(v));

  return (
    <div className="mt-8">
      <h2 className="text-[15px] font-sans font-semibold text-gray-900 mb-4">Stress Test</h2>

      {stressError && (
        <Card className="p-4 mb-4 border border-red-200 bg-red-50">
          <p className="text-sm font-mono text-red-700">{stressError}</p>
        </Card>
      )}

      {stressLoading && (
        <div className="grid grid-cols-3 gap-4 mb-6">
          {[0, 1, 2].map((i) => <div key={i} className="h-28 bg-gray-100 animate-pulse rounded-xl" />)}
        </div>
      )}

      {/* Historical scenario cards */}
      {scenarios.length > 0 && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
            {scenarios.map((sc, i) => {
              const neg = sc.portfolio_return_pct < 0;
              const isActive = activeScenario === i;
              return (
                <button
                  key={sc.scenario_name}
                  onClick={() => setActiveScenario(i)}
                  className={`text-left p-4 rounded-xl border transition-all ${isActive ? "border-indigo-400 bg-indigo-50" : "border-gray-100 bg-white hover:border-gray-200"}`}
                >
                  <div className="flex items-start justify-between mb-1">
                    <span className="text-xs font-semibold text-gray-700">{sc.scenario_label}</span>
                    <span className={`text-xs font-mono font-bold ${neg ? "text-red-600" : "text-emerald-600"}`}>
                      {sc.portfolio_return_pct >= 0 ? "+" : ""}{sc.portfolio_return_pct.toFixed(1)}%
                    </span>
                  </div>
                  <div className="text-[11px] text-gray-400 mb-2">{sc.scenario_start} - {sc.scenario_end}</div>
                  <div className={`text-sm font-mono font-semibold ${neg ? "text-red-600" : "text-emerald-600"}`}>
                    {neg ? "-" : "+"}{fmtINRVal(sc.portfolio_inr_impact)}
                  </div>
                </button>
              );
            })}
          </div>

          {/* Per-holding bar chart for active scenario */}
          {active && (
            <Card className="p-5 mb-6">
              <h3 className="text-sm font-semibold text-gray-600 mb-3">
                {active.scenario_label} - Per-Holding Impact
              </h3>
              <ResponsiveContainer width="100%" height={Math.max(180, active.per_holding.length * 36)}>
                <BarChart
                  data={[...active.per_holding]
                    .sort((a, b) => a.portfolio_contribution_pct - b.portfolio_contribution_pct)
                    .map((holding) => ({
                      ...holding,
                      displayTicker: holding.is_proxy ? `${holding.ticker}, proxy: ${holding.proxy_ticker}` : holding.ticker,
                    }))}
                  layout="vertical"
                  margin={{ top: 4, right: 24, left: 60, bottom: 4 }}
                >
                  <XAxis type="number" tick={{ fontSize: 10 }} tickFormatter={(v) => `${v.toFixed(1)}%`} />
                  <YAxis dataKey="displayTicker" type="category" tick={{ fontSize: 10 }} width={120} />
                  <Tooltip formatter={(v) => [`${v.toFixed(2)}%`, "Portfolio contribution"]} />
                  <Bar dataKey="portfolio_contribution_pct" radius={[0, 4, 4, 0]}>
                    {active.per_holding.map((h) => (
                      <Cell key={h.ticker} fill={h.portfolio_contribution_pct < 0 ? "#ef4444" : "#10b981"} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
              {active.per_holding.some((h) => h.is_proxy) && (
                <p className="text-xs text-amber-600 mt-2">
                  Proxy labels identify holdings whose own price history was unavailable in this window.
                </p>
              )}
            </Card>
          )}
        </>
      )}

      {/* Custom shock */}
      <Card className="p-5">
        <h3 className="text-sm font-semibold text-gray-600 mb-4">Custom Shock Scenario</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-4">
          {[
            { key: "equities_pct", label: "Equities" },
            { key: "crypto_pct", label: "Crypto" },
            { key: "gold_pct", label: "Gold" },
            { key: "bonds_pct", label: "Bonds" },
            { key: "inr_move_pct", label: "INR Move (+ = weaker INR)" },
          ].map(({ key, label }) => (
            <div key={key}>
              <label className="block text-xs text-gray-500 mb-1">{label}: {shock[key]}%</label>
              <input
                type="range" min={-50} max={50} step={1}
                value={shock[key]}
                onChange={(e) => handleShockChange(key, Number(e.target.value))}
                className="w-full accent-indigo-500"
              />
            </div>
          ))}
        </div>
        {customResult && (
          <div className={`p-4 rounded-lg ${customResult.portfolio_return_pct < 0 ? "bg-red-50 border border-red-200" : "bg-emerald-50 border border-emerald-200"}`}>
            <p className={`text-base font-bold font-mono ${customResult.portfolio_return_pct < 0 ? "text-red-700" : "text-emerald-700"}`}>
              Portfolio Impact: {customResult.portfolio_return_pct >= 0 ? "+" : ""}{customResult.portfolio_return_pct.toFixed(1)}%
              {stressData?.portfolio_value_inr ? ` (${customResult.portfolio_inr_impact >= 0 ? "+" : "-"}${fmtINRVal(customResult.portfolio_inr_impact)})` : ""}
            </p>
            <table className="w-full text-xs mt-3">
              <thead><tr className="text-gray-400"><th className="text-left">Ticker</th><th className="text-right">Weight</th><th className="text-right">Shock</th><th className="text-right">Contribution</th></tr></thead>
              <tbody>
                {(customResult.per_holding || []).map((h) => (
                  <tr key={h.ticker} className="border-t border-gray-100">
                    <td className="py-1 font-mono">
                      <span>{h.ticker}</span>
                      {h.is_proxy && (
                        <span className="ml-2 inline-flex rounded-full bg-amber-100 px-1.5 py-0.5 text-[10px] text-amber-700" title="The asset had no price history in this window.">
                          proxy: {h.proxy_ticker}
                        </span>
                      )}
                    </td>
                    <td className="py-1 text-right">{(h.weight * 100).toFixed(1)}%</td>
                    <td className={`py-1 text-right font-mono ${h.shock_pct < 0 ? "text-red-600" : "text-emerald-600"}`}>{h.shock_pct >= 0 ? "+" : ""}{h.shock_pct.toFixed(1)}%</td>
                    <td className={`py-1 text-right font-mono ${h.portfolio_contribution_pct < 0 ? "text-red-600" : "text-emerald-600"}`}>{h.portfolio_contribution_pct >= 0 ? "+" : ""}{h.portfolio_contribution_pct.toFixed(2)}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}