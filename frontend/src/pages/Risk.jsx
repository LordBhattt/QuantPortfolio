import { useState } from "react";

import MonteCarloChart from "../components/charts/MonteCarloChart";
import CorrelationMatrix from "../components/charts/CorrelationMatrix";
import PageWrapper from "../components/layout/PageWrapper";
import Card from "../components/ui-qp/Card";
import EmptyState from "../components/ui-qp/EmptyState";
import { useMonteCarlo, useRiskMetrics } from "../hooks/useRisk";
import { usePortfolioStore } from "../store/portfolioStore";
import { formatINR, formatPct } from "../utils/format";

const HORIZONS = ["3M", "6M", "1Y", "3Y"];
const HORIZON_DAYS = { "3M": 63, "6M": 126, "1Y": 252, "3Y": 756 };
const N_PATHS = 1000;

function SkeletonBlock({ className }) {
  return <div className={`bg-gray-100 animate-pulse rounded-xl ${className}`} />;
}

export default function Risk() {
  const portfolioId = usePortfolioStore((s) => s.portfolioId);
  const [horizon, setHorizon] = useState("1Y");

  const { data: risk, loading: riskLoading, error: riskError } = useRiskMetrics(portfolioId);
  const { data: mc, loading: mcLoading, error: mcError } = useMonteCarlo(portfolioId, N_PATHS, HORIZON_DAYS[horizon]);

  const isLoading = portfolioId && (riskLoading || mcLoading);
  const probLoss = (mc?.prob_loss ?? 0) * 100;
  const probColor = probLoss >= 30 ? "text-red-600" : probLoss >= 10 ? "text-amber-600" : "text-gray-900";
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

              <div className="mt-6 pt-5 border-t border-black/[0.06] flex items-end justify-between flex-wrap gap-4">
                <div>
                  <div className="text-[11px] font-sans font-semibold tracking-[0.14em] uppercase text-gray-400">Probability of Loss</div>
                  <div className={`mt-1 text-4xl font-mono font-bold ${probColor}`}>{probLoss.toFixed(1)}%</div>
                </div>
                <div className="text-right text-xs font-mono text-gray-500">over a {horizon} horizon vs today&apos;s value</div>
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
    </PageWrapper>
  );
}
