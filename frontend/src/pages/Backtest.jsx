import { useMemo, useState } from "react";

import BacktestDrawdownChart from "../components/charts/BacktestDrawdownChart";
import BacktestEquityChart, { STRATEGY_LABELS } from "../components/charts/BacktestEquityChart";
import RegimeStrip from "../components/charts/RegimeStrip";
import PageWrapper from "../components/layout/PageWrapper";
import Card from "../components/ui-qp/Card";
import EmptyState from "../components/ui-qp/EmptyState";
import { useBacktest } from "../hooks/useBacktest";
import { formatPct } from "../utils/format";

const CHART_MAX_POINTS = 320;
const DEFAULT_COMPARISON_STRATEGY = "full_pipeline";

function SkeletonBlock({ className }) {
  return <div className={`bg-gray-100 animate-pulse rounded-xl ${className}`} />;
}

function downsample(points, maxPoints) {
  if (points.length <= maxPoints) return points;
  const step = Math.ceil(points.length / maxPoints);
  return points.filter((_, index) => index % step === 0);
}

function buildEquityChartData(strategies) {
  const dateMap = new Map();
  for (const strategy of strategies) {
    for (const point of downsample(strategy.equity_curve, CHART_MAX_POINTS)) {
      const entry = dateMap.get(point.date) || { date: point.date };
      entry[strategy.name] = point.value;
      dateMap.set(point.date, entry);
    }
  }
  return Array.from(dateMap.values()).sort((a, b) => (a.date < b.date ? -1 : a.date > b.date ? 1 : 0));
}

function buildDrawdownChartData(strategy) {
  if (!strategy) return [];
  let peak = -Infinity;
  const withDrawdown = strategy.equity_curve.map((point) => {
    peak = Math.max(peak, point.value);
    return { date: point.date, [strategy.name]: peak > 0 ? point.value / peak - 1 : 0 };
  });
  return downsample(withDrawdown, CHART_MAX_POINTS);
}

const METRIC_COLUMNS = [
  { key: "cagr", label: "CAGR", format: (v) => formatPct(v) },
  { key: "sharpe", label: "Sharpe", format: (v) => Number(v).toFixed(2) },
  { key: "sortino", label: "Sortino", format: (v) => Number(v).toFixed(2) },
  { key: "calmar", label: "Calmar", format: (v) => Number(v).toFixed(2) },
  { key: "max_drawdown", label: "Max Drawdown", format: (v) => formatPct(v) },
  { key: "avg_turnover", label: "Avg Turnover", format: (v) => formatPct(v) },
];

export default function Backtest() {
  const [comparisonStrategy, setComparisonStrategy] = useState(DEFAULT_COMPARISON_STRATEGY);
  const { data, loading, error } = useBacktest();

  const strategies = data?.strategies ?? [];
  const strategyNames = useMemo(() => strategies.map((s) => s.name), [strategies]);
  const equityChartData = useMemo(() => buildEquityChartData(strategies), [strategies]);

  const activeStrategy = strategies.find((s) => s.name === comparisonStrategy) || strategies[0];
  const drawdownChartData = useMemo(() => buildDrawdownChartData(activeStrategy), [activeStrategy]);
  const regimePoints = activeStrategy?.equity_curve ?? [];

  const isMissingDataset = error?.toLowerCase().includes("dataset") || error?.toLowerCase().includes("cache");

  return (
    <PageWrapper
      title="Backtest"
      subtitle={data ? `Walk-forward study on historical data through ${data.data_through} · not a live view` : "Walk-forward strategy validation"}
    >
      {error && !loading && (
        <Card className="p-6 mb-6">
          {isMissingDataset ? (
            <EmptyState
              title="Historical dataset not built yet"
              subtitle="Run `python -m backend.scripts.build_backtest_dataset` once on the backend to populate the local historical cache used by this page."
            />
          ) : (
            <p className="text-sm font-mono text-red-700">{error}</p>
          )}
        </Card>
      )}

      {!error && (
        <>
          <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-5">
            {loading || !data
              ? Array.from({ length: 5 }).map((_, index) => <SkeletonBlock key={index} className="h-24 w-full" />)
              : strategies.map((strategy, index) => {
                  const isBaseline = strategy.name === data.baseline;
                  const isProduction = strategy.name === "full_pipeline";
                  return (
                    <Card key={strategy.name} className={`p-4 ${isProduction ? "border-primary/40" : ""}`}>
                      <div className="text-[10px] font-sans font-semibold uppercase tracking-[0.12em] text-gray-400">
                        {STRATEGY_LABELS[strategy.name] || strategy.name}
                        {isBaseline && <span className="ml-1 text-gray-300">(baseline)</span>}
                      </div>
                      <div className="mt-2 font-mono text-xl font-bold text-gray-900">{formatPct(strategy.metrics.cagr)}</div>
                      <div className="mt-1 text-xs font-mono text-gray-500">CAGR &middot; Sharpe {strategy.metrics.sharpe.toFixed(2)}</div>
                    </Card>
                  );
                })}
          </div>

          <div className="mb-6 animate-fadeUp opacity-0" style={{ animationDelay: "120ms" }}>
            <Card className="p-5 min-h-[420px]">
              <div className="mb-4">
                <h2 className="text-[15px] font-sans font-semibold text-gray-900">Out-of-Sample Equity Curves</h2>
                <p className="mt-0.5 text-xs font-mono text-gray-500">
                  Walk-forward, monthly rebalanced, no lookahead &middot; growth of ₹1 invested
                </p>
              </div>
              {loading || !data ? <SkeletonBlock className="h-[340px] w-full" /> : <BacktestEquityChart data={equityChartData} strategies={strategyNames} />}
            </Card>
          </div>

          <div className="mb-6 grid grid-cols-1 gap-4 lg:grid-cols-3">
            <div className="lg:col-span-2 animate-fadeUp opacity-0" style={{ animationDelay: "180ms" }}>
              <Card className="p-5 h-full">
                <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 className="text-[15px] font-sans font-semibold text-gray-900">Drawdown &amp; Regime Timeline</h2>
                    <p className="mt-0.5 text-xs font-mono text-gray-500">Detected market regime per rebalance period</p>
                  </div>
                  {!loading && data && (
                    <div className="inline-flex items-center border border-black/[0.08] rounded-full p-0.5">
                      {strategyNames.map((name) => (
                        <button
                          key={name}
                          onClick={() => setComparisonStrategy(name)}
                          className={`px-3 py-1 text-[11px] font-mono font-medium rounded-full transition-colors ${
                            comparisonStrategy === name ? "bg-gray-900 text-white" : "text-gray-500 hover:text-gray-900"
                          }`}
                        >
                          {STRATEGY_LABELS[name] || name}
                        </button>
                      ))}
                    </div>
                  )}
                </div>

                {loading || !data ? (
                  <SkeletonBlock className="h-[160px] w-full" />
                ) : (
                  <>
                    <BacktestDrawdownChart data={drawdownChartData} strategyKey={comparisonStrategy} />
                    <div className="mt-4">
                      <RegimeStrip points={regimePoints} />
                    </div>
                  </>
                )}
              </Card>
            </div>

            <div className="animate-fadeUp opacity-0" style={{ animationDelay: "240ms" }}>
              <Card className="p-5 h-full">
                <h2 className="text-[15px] font-sans font-semibold text-gray-900 mb-1">Significance vs. Baseline</h2>
                <p className="text-xs font-mono text-gray-500 mb-4">Block-bootstrap 95% CI on Sharpe difference</p>
                {loading || !data ? (
                  <div className="space-y-3">
                    {Array.from({ length: 4 }).map((_, index) => (
                      <SkeletonBlock key={index} className="h-10 w-full" />
                    ))}
                  </div>
                ) : data.significance_vs_baseline.length === 0 ? (
                  <EmptyState title="No comparisons available" subtitle="Not enough overlapping history for a bootstrap test." />
                ) : (
                  <div className="space-y-3">
                    {data.significance_vs_baseline.map((entry) => (
                      <div key={entry.strategy} className="flex items-baseline justify-between border-b border-black/[0.04] pb-2 last:border-0">
                        <span className="text-[11px] font-sans font-medium text-gray-600">{STRATEGY_LABELS[entry.strategy] || entry.strategy}</span>
                        <span className={`font-mono text-xs ${entry.significant ? "text-primary font-semibold" : "text-gray-900"}`}>
                          {entry.observed_difference >= 0 ? "+" : ""}
                          {entry.observed_difference.toFixed(2)} [{entry.ci_lower.toFixed(2)}, {entry.ci_upper.toFixed(2)}]
                        </span>
                      </div>
                    ))}
                  </div>
                )}
              </Card>
            </div>
          </div>

          <div className="animate-fadeUp opacity-0" style={{ animationDelay: "300ms" }}>
            <Card className="p-5 overflow-x-auto">
              <h2 className="text-[15px] font-sans font-semibold text-gray-900 mb-4">Strategy Comparison</h2>
              {loading || !data ? (
                <SkeletonBlock className="h-40 w-full" />
              ) : (
                <table className="w-full min-w-[640px] text-sm">
                  <thead>
                    <tr className="border-b border-black/[0.06]">
                      <th className="py-2 text-left text-[11px] font-sans font-semibold uppercase tracking-[0.1em] text-gray-400">Strategy</th>
                      {METRIC_COLUMNS.map((column) => (
                        <th key={column.key} className="py-2 text-right text-[11px] font-sans font-semibold uppercase tracking-[0.1em] text-gray-400">
                          {column.label}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {strategies.map((strategy) => (
                      <tr key={strategy.name} className="border-b border-black/[0.04] last:border-0">
                        <td className="py-2.5 font-mono text-xs text-gray-900">{STRATEGY_LABELS[strategy.name] || strategy.name}</td>
                        {METRIC_COLUMNS.map((column) => (
                          <td key={column.key} className="py-2.5 text-right font-mono text-xs text-gray-900">
                            {column.format(strategy.metrics[column.key])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Card>
          </div>
        </>
      )}
    </PageWrapper>
  );
}
