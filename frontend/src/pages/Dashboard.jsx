import { useMemo, useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import {
  AreaChart, Area, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";

import BenchmarkComparisonChart from "../components/charts/BenchmarkComparisonChart";
import PerformanceChart from "../components/charts/PerformanceChart";
import AllocationDonut from "../components/charts/AllocationDonut";
import HeroBand from "../components/dashboard/HeroBand";
import { InvestedVsCurrentCard, RiskSnapshotCard, TotalReturnCard } from "../components/dashboard/StatCards";
import HoldingsTable from "../components/domain/HoldingsTable";
import PageWrapper from "../components/layout/PageWrapper";
import Card from "../components/ui-qp/Card";
import EmptyState from "../components/ui-qp/EmptyState";
import { useAnalytics } from "../hooks/useAnalytics";
import { useHoldings } from "../hooks/usePortfolio";
import { useRiskMetrics } from "../hooks/useRisk";
import { mapAllocationData, mergeHoldingsWithAnalytics } from "../lib/portfolioMappers";
import { usePortfolioStore } from "../store/portfolioStore";
import { getRegimeHistory } from "../api/regime";

const RANGES = ["7D", "1M", "3M", "1Y"];
const RANGE_LEN = { "7D": 7, "1M": 30, "3M": 90, "1Y": 365 };
const CHART_TABS = [
  { id: "benchmark", label: "Benchmark" },
  { id: "value", label: "Value" },
];

function SkeletonBlock({ className }) {
  return <div className={`bg-gray-100 animate-pulse rounded-xl ${className}`} />;
}

export default function Dashboard() {
  const navigate = useNavigate();
  const portfolioId = usePortfolioStore((s) => s.portfolioId);
  const regime = usePortfolioStore((s) => s.regime);
  const [range, setRange] = useState("3M");
  const [chartTab, setChartTab] = useState("benchmark");

  const { data: analytics, loading: analyticsLoading, error: analyticsError } = useAnalytics(portfolioId);
  const { data: holdings, loading: holdingsLoading } = useHoldings(portfolioId);
  const { data: risk, loading: riskLoading } = useRiskMetrics(portfolioId);

  const heroLoading = Boolean(portfolioId) && analyticsLoading;
  const summaryLoading = Boolean(portfolioId) && analyticsLoading;
  const chartLoading = Boolean(portfolioId) && analyticsLoading;
  const allocationLoading = Boolean(portfolioId) && analyticsLoading;
  const holdingsTableLoading = Boolean(portfolioId) && holdingsLoading;
  const holdingsList = holdings || [];
  const empty = !holdingsTableLoading && holdingsList.length === 0;
  const perfSource = analytics?.performance_series || [];
  const benchmarkSource = analytics?.benchmark_series || [];
  const perf = perfSource.slice(-RANGE_LEN[range]);
  const sparkData = perfSource.slice(-30).map((point) => point.portfolio);
  const allocation = mapAllocationData(analytics?.asset_class_allocation);
  const mergedHoldings = useMemo(() => mergeHoldingsWithAnalytics(holdingsList, analytics), [holdingsList, analytics]);
  const benchmarkLatest = benchmarkSource.at(-1);

  const total = analytics?.total_value_inr ?? 0;
  const totalPnl = analytics?.total_pnl_inr ?? 0;
  const invested = analytics?.total_invested_inr ?? Math.max(total - totalPnl, 0);
  const dayChange = analytics?.day_pnl_inr ?? 0;
  const dayChangePct = (analytics?.day_pnl_pct ?? 0) * 100;
  const totalReturnPct = (analytics?.total_pnl_pct ?? 0) * 100;
  const annualisedReturnPct = (risk?.annualised_return ?? analytics?.total_pnl_pct ?? 0) * 100;
  const asOfDate = analytics?.as_of ? new Date(analytics.as_of) : new Date();
  const asOf = `As of ${new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(asOfDate)}`;

  return (
    <PageWrapper title="Dashboard" subtitle="Portfolio overview - live market view">
      {analyticsError && !empty && !chartLoading && (
        <Card className="p-4 mb-6 border border-red-200 bg-red-50">
          <p className="text-sm font-mono text-red-700">{analyticsError}</p>
        </Card>
      )}

      <div className="animate-fadeUp opacity-0 mb-6" style={{ animationDelay: "0ms" }}>
        {heroLoading ? (
          <SkeletonBlock className="h-56 w-full" />
        ) : (
          <HeroBand
            totalValue={total}
            dayChange={dayChange}
            dayChangePct={dayChangePct}
            asOf={asOf}
            sparkData={sparkData}
            empty={empty}
            onAdd={() => navigate("/holdings")}
          />
        )}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div className="animate-fadeUp opacity-0" style={{ animationDelay: "60ms" }}>
          {summaryLoading ? (
            <SkeletonBlock className="h-40 w-full" />
          ) : (
            <InvestedVsCurrentCard invested={invested} current={total} />
          )}
        </div>
        <div className="animate-fadeUp opacity-0" style={{ animationDelay: "120ms" }}>
          {summaryLoading ? (
            <SkeletonBlock className="h-40 w-full" />
          ) : (
            <TotalReturnCard returnPct={totalReturnPct} absoluteGain={totalPnl} xirr={annualisedReturnPct} />
          )}
        </div>
        <div className="animate-fadeUp opacity-0" style={{ animationDelay: "180ms" }}>
          {riskLoading ? (
            <SkeletonBlock className="h-40 w-full" />
          ) : (
            <RiskSnapshotCard
              sharpe={risk?.sharpe_ratio ?? 0}
              maxDD={(risk?.max_drawdown ?? 0) * 100}
              beta={risk?.beta ?? 0}
              regime={regime || "sideways"}
            />
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <div className="lg:col-span-2 animate-fadeUp opacity-0" style={{ animationDelay: "240ms" }}>
          <Card className="p-5">
            <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <h2 className="text-[15px] font-sans font-semibold text-gray-900">Performance</h2>
                <p className="text-xs font-mono text-gray-500 mt-0.5">
                  {chartTab === "benchmark" ? "Rolling 6M comparison vs NIFTY 50 and S&P 500" : "Portfolio value vs cost basis"}
                </p>
              </div>
              <div className="inline-flex items-center border border-black/[0.08] rounded-full p-0.5 self-start">
                {CHART_TABS.map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => setChartTab(tab.id)}
                    className={`px-4 py-1 text-[11px] font-mono font-medium rounded-full transition-colors ${
                      chartTab === tab.id ? "bg-gray-900 text-white" : "text-gray-500 hover:text-gray-900"
                    }`}
                  >
                    {tab.label}
                  </button>
                ))}
              </div>
            </div>
            {chartLoading ? (
              <SkeletonBlock className="h-[300px] w-full" />
            ) : chartTab === "benchmark" ? (
              benchmarkSource.length > 0 ? (
                <div>
                  <BenchmarkComparisonChart data={benchmarkSource} />
                  {benchmarkLatest && (
                    <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-2">
                      <div className="rounded-xl border border-black/[0.06] bg-gray-50 px-3 py-2">
                        <div className="text-[10px] font-mono uppercase tracking-[0.14em] text-gray-400">Portfolio</div>
                        <div className="mt-1 font-mono text-sm font-semibold text-gray-900">
                          {((benchmarkLatest.portfolio || 0) * 100).toFixed(1)}%
                        </div>
                      </div>
                      <div className="rounded-xl border border-black/[0.06] bg-gray-50 px-3 py-2">
                        <div className="text-[10px] font-mono uppercase tracking-[0.14em] text-gray-400">NIFTY 50</div>
                        <div className="mt-1 font-mono text-sm font-semibold text-gray-900">
                          {((benchmarkLatest.nifty50 || 0) * 100).toFixed(1)}%
                        </div>
                      </div>
                      <div className="rounded-xl border border-black/[0.06] bg-gray-50 px-3 py-2">
                        <div className="text-[10px] font-mono uppercase tracking-[0.14em] text-gray-400">S&P 500</div>
                        <div className="mt-1 font-mono text-sm font-semibold text-gray-900">
                          {((benchmarkLatest.sp500 || 0) * 100).toFixed(1)}%
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              ) : (
                <EmptyState title="Benchmark data unavailable" subtitle="We couldn’t load the 6M benchmark comparison yet." />
              )
            ) : (
              perf.length > 0 ? (
                <PerformanceChart data={perf} costBasis={invested} />
              ) : (
                <EmptyState title="No performance history yet" subtitle="Add holdings to start tracking performance." />
              )
            )}
            {chartTab === "value" && (
              <div className="mt-4 flex justify-center">
                <div className="inline-flex items-center border border-black/[0.08] rounded-full p-0.5">
                  {RANGES.map((token) => (
                    <button
                      key={token}
                      onClick={() => setRange(token)}
                      className={`px-4 py-1 text-[11px] font-mono font-medium rounded-full transition-colors ${
                        range === token ? "bg-gray-900 text-white" : "text-gray-500 hover:text-gray-900"
                      }`}
                    >
                      {token}
                    </button>
                  ))}
                </div>
              </div>
            )}
          </Card>
        </div>

        <div className="animate-fadeUp opacity-0" style={{ animationDelay: "300ms" }}>
          <Card className="p-5 h-full">
            <h2 className="text-[15px] font-sans font-semibold text-gray-900 mb-4">Allocation</h2>
            {allocationLoading ? (
              <SkeletonBlock className="h-[300px] w-full" />
            ) : allocation.length > 0 ? (
              <AllocationDonut data={allocation} />
            ) : (
              <EmptyState title="No allocation yet" subtitle="Portfolio allocation will appear after you add holdings." />
            )}
          </Card>
        </div>
      </div>

      <div className="animate-fadeUp opacity-0" style={{ animationDelay: "360ms" }}>
        <Card className="p-5">
          <h2 className="text-[15px] font-sans font-semibold text-gray-900 mb-4">Holdings</h2>
          <HoldingsTable
            holdings={mergedHoldings.slice(0, 5)}
            loading={holdingsTableLoading}
            onAdd={() => navigate("/holdings")}
          />
        </Card>
      </div>

      <RegimeHistoryChart />

      <div className="animate-fadeUp opacity-0" style={{ animationDelay: "420ms" }}>
        <Card className="p-4 border border-indigo-100 bg-indigo-50/40">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-sm font-semibold text-indigo-900">Model Track Record</h3>
              <p className="text-xs text-indigo-600 mt-0.5">Walk-forward backtest - no lookahead data</p>
            </div>
            <Link
              to="/backtest"
              className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 underline-offset-2 hover:underline"
            >
              View Backtest Lab
            </Link>
          </div>
        </Card>
      </div>
    </PageWrapper>
  );
}

const REGIME_COLORS = { bull: "#10b981", sideways: "#f59e0b", bear: "#ef4444" };
const REGIME_BG = { bull: "rgba(16,185,129,0.12)", sideways: "rgba(245,158,11,0.12)", bear: "rgba(239,68,68,0.12)" };

function RegimeHistoryChart() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getRegimeHistory(252)
      .then((d) => setData(d || []))
      .catch(() => setData([]))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="animate-fadeUp opacity-0 mt-4" style={{ animationDelay: "400ms" }}>
        <div className="h-40 bg-gray-100 animate-pulse rounded-xl" />
      </div>
    );
  }
  if (!data.length) return null;

  const sampled = data.filter((_, i) => i % 3 === 0 || i === data.length - 1);

  return (
    <div className="animate-fadeUp opacity-0 mt-4" style={{ animationDelay: "400ms" }}>
      <Card className="p-5">
        <h2 className="text-[15px] font-sans font-semibold text-gray-900 mb-1">Market Regime - SPY</h2>
        <p className="text-xs text-gray-400 mb-3 font-mono">Bull / Sideways / Bear - last 252 trading days</p>
        <ResponsiveContainer width="100%" height={160}>
          <AreaChart data={sampled} margin={{ top: 4, right: 8, left: 0, bottom: 4 }}>
            <defs>
              {["bull", "sideways", "bear"].map((r) => (
                <linearGradient key={r} id={`grad-${r}`} x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor={REGIME_COLORS[r]} stopOpacity={0.3} />
                  <stop offset="95%" stopColor={REGIME_COLORS[r]} stopOpacity={0.0} />
                </linearGradient>
              ))}
            </defs>
            <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
            <XAxis dataKey="date" tick={{ fontSize: 9 }} tickFormatter={(d) => d?.slice(0, 7)} />
            <YAxis tick={{ fontSize: 9 }} tickFormatter={(v) => `$${v.toFixed(0)}`} />
            <Tooltip
              formatter={(v, name) => [name === "close" ? `$${v.toFixed(2)}` : v, name]}
              labelFormatter={(l) => `Date: ${l}`}
            />
            <Area
              type="monotone"
              dataKey="close"
              stroke="#6366f1"
              fill="url(#grad-bull)"
              dot={false}
              strokeWidth={1.5}
            />
          </AreaChart>
        </ResponsiveContainer>
        <div className="flex gap-4 mt-2 text-xs font-mono">
          {["bull", "sideways", "bear"].map((r) => (
            <span key={r} className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full inline-block" style={{ background: REGIME_COLORS[r] }} />
              <span className="capitalize text-gray-500">{r}</span>
            </span>
          ))}
        </div>
      </Card>
    </div>
  );
}
