import FactorBar from "../components/charts/FactorBar";
import PageWrapper from "../components/layout/PageWrapper";
import AssetClassPill from "../components/ui-qp/AssetClassPill";
import Card from "../components/ui-qp/Card";
import EmptyState from "../components/ui-qp/EmptyState";
import PnLPill from "../components/ui-qp/PnLPill";
import { useAnalytics } from "../hooks/useAnalytics";
import { mapFactorExposure } from "../lib/portfolioMappers";
import { usePortfolioStore } from "../store/portfolioStore";

function SkeletonBlock({ className }) {
  return <div className={`bg-gray-100 animate-pulse rounded-xl ${className}`} />;
}

export default function Analytics() {
  const portfolioId = usePortfolioStore((s) => s.portfolioId);
  const { data, loading, error } = useAnalytics(portfolioId);

  const factorData = mapFactorExposure(data?.factor_exposure);
  const returnAttribution = (data?.holdings_breakdown || []).map((item) => ({
    ticker: item.ticker,
    cls: item.asset_class,
    contribPct: Number(item.contribution_to_return || 0) * 100,
    positive: Number(item.contribution_to_return || 0) >= 0,
  }));

  const totalRiskContribution = (data?.holdings_breakdown || []).reduce(
    (sum, item) => sum + Math.abs(Number(item.contribution_to_risk || 0)),
    0,
  );
  const riskAttribution = (data?.holdings_breakdown || []).map((item) => ({
    ticker: item.ticker,
    cls: item.asset_class,
    contribPct: totalRiskContribution > 0 ? (Math.abs(Number(item.contribution_to_risk || 0)) / totalRiskContribution) * 100 : 0,
  }));

  const maxReturnContrib = Math.max(1, ...returnAttribution.map((item) => Math.abs(item.contribPct)));
  const maxRiskContrib = Math.max(1, ...riskAttribution.map((item) => item.contribPct));
  const empty = error?.toLowerCase().includes("no holdings");

  return (
    <PageWrapper title="Analytics" subtitle="Factor exposure and attribution">
      {error && !empty && !loading && (
        <Card className="p-4 mb-6 border border-red-200 bg-red-50">
          <p className="text-sm font-mono text-red-700">{error}</p>
        </Card>
      )}

      {empty && !loading ? (
        <Card className="p-6">
          <EmptyState title="No holdings to analyze yet" subtitle="Add holdings to unlock factor exposure and attribution." />
        </Card>
      ) : (
        <>
          <div className="animate-fadeUp opacity-0 mb-6" style={{ animationDelay: "0ms" }}>
            <Card className="p-5">
              <div className="flex items-start justify-between mb-4">
                <div>
                  <h2 className="text-[15px] font-sans font-semibold text-gray-900">Factor Exposure</h2>
                  <p className="text-xs font-mono text-gray-500 mt-0.5">Fama-French 5-Factor Model</p>
                </div>
                <span className="font-mono text-[10px] uppercase tracking-wider px-2 py-1 bg-primary/10 text-primary rounded">
                  R2 = {data?.factor_exposure?.r_squared?.toFixed(2) ?? "0.00"}
                </span>
              </div>
              {loading ? <SkeletonBlock className="h-[260px] w-full" /> : <FactorBar data={factorData} />}
            </Card>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="animate-fadeUp opacity-0" style={{ animationDelay: "120ms" }}>
              <Card className="p-5">
                <h2 className="text-[15px] font-sans font-semibold text-gray-900 mb-4">Return Attribution</h2>
                {loading ? (
                  <div className="space-y-3">
                    {Array.from({ length: 5 }).map((_, index) => (
                      <SkeletonBlock key={index} className="h-12 w-full" />
                    ))}
                  </div>
                ) : returnAttribution.length > 0 ? (
                  <div className="space-y-2">
                    {returnAttribution.map((item) => (
                      <div key={item.ticker} className="grid grid-cols-[1fr_80px_1fr_80px] items-center gap-3 py-1.5">
                        <span className="font-mono text-sm font-semibold uppercase tracking-wider text-gray-900 truncate">{item.ticker}</span>
                        <AssetClassPill cls={item.cls} />
                        <div className="h-2 bg-black/[0.06] rounded-full overflow-hidden">
                          <div
                            className={`h-full rounded-full ${item.positive ? "bg-gray-900" : "bg-gray-300"}`}
                            style={{ width: `${(Math.abs(item.contribPct) / maxReturnContrib) * 100}%` }}
                          />
                        </div>
                        <div className="justify-self-end">
                          <PnLPill positive={item.positive}>
                            {item.contribPct >= 0 ? "+" : ""}{item.contribPct.toFixed(2)}%
                          </PnLPill>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState title="No attribution yet" subtitle="Return attribution will appear after holdings are analyzed." />
                )}
              </Card>
            </div>

            <div className="animate-fadeUp opacity-0" style={{ animationDelay: "180ms" }}>
              <Card className="p-5">
                <h2 className="text-[15px] font-sans font-semibold text-gray-900 mb-4">Risk Attribution</h2>
                {loading ? (
                  <div className="space-y-3">
                    {Array.from({ length: 5 }).map((_, index) => (
                      <SkeletonBlock key={index} className="h-12 w-full" />
                    ))}
                  </div>
                ) : riskAttribution.length > 0 ? (
                  <div className="space-y-2">
                    {riskAttribution.map((item) => (
                      <div key={item.ticker} className="grid grid-cols-[1fr_80px_1fr_60px] items-center gap-3 py-1.5">
                        <span className="font-mono text-sm font-semibold uppercase tracking-wider text-gray-900 truncate">{item.ticker}</span>
                        <AssetClassPill cls={item.cls} />
                        <div className="h-2 bg-black/[0.06] rounded-full overflow-hidden">
                          <div className="h-full bg-primary rounded-full" style={{ width: `${(item.contribPct / maxRiskContrib) * 100}%` }} />
                        </div>
                        <span className="font-mono text-sm text-right text-gray-900">{item.contribPct.toFixed(1)}%</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState title="No risk attribution yet" subtitle="Risk attribution will appear after holdings are analyzed." />
                )}
              </Card>
            </div>
          </div>
        </>
      )}
    </PageWrapper>
  );
}
