import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

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

const RANGES = ["7D", "1M", "3M", "1Y"];
const RANGE_LEN = { "7D": 7, "1M": 30, "3M": 90, "1Y": 365 };

function SkeletonBlock({ className }) {
  return <div className={`bg-gray-100 animate-pulse rounded-xl ${className}`} />;
}

export default function Dashboard() {
  const navigate = useNavigate();
  const portfolioId = usePortfolioStore((s) => s.portfolioId);
  const regime = usePortfolioStore((s) => s.regime);
  const [range, setRange] = useState("3M");

  const { data: analytics, loading: analyticsLoading, error: analyticsError } = useAnalytics(portfolioId);
  const { data: holdings, loading: holdingsLoading } = useHoldings(portfolioId);
  const { data: risk, loading: riskLoading } = useRiskMetrics(portfolioId);

  const isLoading = portfolioId && (analyticsLoading || holdingsLoading || riskLoading);
  const holdingsList = holdings || [];
  const empty = !holdingsLoading && holdingsList.length === 0;
  const perfSource = analytics?.performance_series || [];
  const perf = perfSource.slice(-RANGE_LEN[range]);
  const sparkData = perfSource.slice(-30).map((point) => point.portfolio);
  const allocation = mapAllocationData(analytics?.asset_class_allocation);
  const mergedHoldings = useMemo(() => mergeHoldingsWithAnalytics(holdingsList, analytics), [holdingsList, analytics]);

  const total = analytics?.total_value_inr ?? 0;
  const totalPnl = analytics?.total_pnl_inr ?? 0;
  const invested = Math.max(total - totalPnl, 0);
  const dayChange = analytics?.day_pnl_inr ?? 0;
  const dayChangePct = (analytics?.day_pnl_pct ?? 0) * 100;
  const totalReturnPct = (analytics?.total_pnl_pct ?? 0) * 100;
  const annualisedReturnPct = (risk?.annualised_return ?? analytics?.total_pnl_pct ?? 0) * 100;
  const asOf = `As of ${new Intl.DateTimeFormat("en-IN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date())}`;

  return (
    <PageWrapper title="Dashboard" subtitle="Portfolio overview - live market view">
      {analyticsError && !empty && !isLoading && (
        <Card className="p-4 mb-6 border border-red-200 bg-red-50">
          <p className="text-sm font-mono text-red-700">{analyticsError}</p>
        </Card>
      )}

      <div className="animate-fadeUp opacity-0 mb-6" style={{ animationDelay: "0ms" }}>
        {isLoading ? (
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
          {isLoading ? (
            <SkeletonBlock className="h-40 w-full" />
          ) : (
            <InvestedVsCurrentCard invested={invested} current={total} />
          )}
        </div>
        <div className="animate-fadeUp opacity-0" style={{ animationDelay: "120ms" }}>
          {isLoading ? (
            <SkeletonBlock className="h-40 w-full" />
          ) : (
            <TotalReturnCard returnPct={totalReturnPct} absoluteGain={totalPnl} xirr={annualisedReturnPct} />
          )}
        </div>
        <div className="animate-fadeUp opacity-0" style={{ animationDelay: "180ms" }}>
          {isLoading ? (
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
            <div className="mb-4">
              <h2 className="text-[15px] font-sans font-semibold text-gray-900">Performance</h2>
              <p className="text-xs font-mono text-gray-500 mt-0.5">Portfolio vs Benchmark</p>
            </div>
            {isLoading ? (
              <SkeletonBlock className="h-[300px] w-full" />
            ) : perf.length > 0 ? (
              <PerformanceChart data={perf} costBasis={invested} />
            ) : (
              <EmptyState title="No performance history yet" subtitle="Add holdings to start tracking performance." />
            )}
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
          </Card>
        </div>

        <div className="animate-fadeUp opacity-0" style={{ animationDelay: "300ms" }}>
          <Card className="p-5 h-full">
            <h2 className="text-[15px] font-sans font-semibold text-gray-900 mb-4">Allocation</h2>
            {isLoading ? (
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
            loading={Boolean(isLoading)}
            onAdd={() => navigate("/holdings")}
          />
        </Card>
      </div>
    </PageWrapper>
  );
}
