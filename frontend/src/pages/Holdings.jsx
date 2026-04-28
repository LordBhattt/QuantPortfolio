import { useMemo, useState } from "react";

import { addHolding, deleteHolding } from "../api/portfolios";
import AddHoldingDrawer from "../components/domain/AddHoldingDrawer";
import HoldingsTable from "../components/domain/HoldingsTable";
import PageWrapper from "../components/layout/PageWrapper";
import Card from "../components/ui-qp/Card";
import { useAnalytics } from "../hooks/useAnalytics";
import { useHoldings } from "../hooks/usePortfolio";
import { mergeHoldingsWithAnalytics } from "../lib/portfolioMappers";
import { usePortfolioStore } from "../store/portfolioStore";

const CLASSES = ["ALL", "STOCKS", "CRYPTO", "GOLD", "MF/ETF", "BONDS"];
const CLASS_MAP = {
  STOCKS: "Stock",
  CRYPTO: "Crypto",
  GOLD: "Gold",
  "MF/ETF": "MF/ETF",
  BONDS: "Bond",
};

export default function Holdings() {
  const portfolioId = usePortfolioStore((s) => s.portfolioId);
  const [filter, setFilter] = useState("ALL");
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [search, setSearch] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const { data: holdings, loading, refetch } = useHoldings(portfolioId);
  const { data: analytics, loading: analyticsLoading, refetch: refetchAnalytics } = useAnalytics(portfolioId);

  const tableData = useMemo(() => mergeHoldingsWithAnalytics(holdings || [], analytics), [holdings, analytics]);
  const filtered = useMemo(() => {
    return tableData.filter((holding) => {
      if (filter !== "ALL" && holding.cls !== CLASS_MAP[filter]) return false;
      if (search) {
        const term = search.toLowerCase();
        if (!holding.ticker.toLowerCase().includes(term) && !String(holding.name || "").toLowerCase().includes(term)) {
          return false;
        }
      }
      return true;
    });
  }, [filter, search, tableData]);

  const refreshAll = async () => {
    await Promise.all([refetch(), refetchAnalytics()]);
  };

  const handleAdd = async (payload) => {
    if (!portfolioId) {
      setError("Create or select a portfolio before adding holdings.");
      return;
    }

    setSubmitting(true);
    setError(null);
    try {
      await addHolding(portfolioId, payload);
      setDrawerOpen(false);
      await refreshAll();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to add holding");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (holding) => {
    if (!portfolioId) return;
    setError(null);
    try {
      await deleteHolding(portfolioId, holding.id);
      await refreshAll();
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to delete holding");
    }
  };

  return (
    <PageWrapper title="Holdings" subtitle="All positions across asset classes">
      <div className="animate-fadeUp opacity-0" style={{ animationDelay: "0ms" }}>
        <Card className="p-5">
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <input
              type="text"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search ticker..."
              className="flex-1 min-w-[180px] max-w-xs px-3 py-2 text-sm font-mono border border-black/[0.1] rounded-lg outline-none focus:border-primary transition-colors placeholder:text-gray-400"
            />

            <div className="flex items-center gap-1 flex-wrap">
              {CLASSES.map((cls) => (
                <button
                  key={cls}
                  onClick={() => setFilter(cls)}
                  className={`px-3 py-1.5 text-[11px] font-mono font-medium tracking-wider rounded-lg transition-colors ${
                    filter === cls ? "bg-gray-900 text-white" : "text-gray-500 hover:text-gray-900 hover:bg-black/[0.04]"
                  }`}
                >
                  {cls}
                </button>
              ))}
            </div>

            <button
              onClick={() => setDrawerOpen(true)}
              className="ml-auto px-4 py-2 bg-gray-900 text-white text-sm font-sans font-semibold rounded-lg hover:opacity-90 transition-opacity"
            >
              + Add Holding
            </button>
          </div>

          {error && <p className="mb-4 text-sm font-mono text-red-600">{error}</p>}

          <HoldingsTable
            holdings={filtered}
            loading={Boolean(loading || analyticsLoading)}
            onAdd={() => setDrawerOpen(true)}
            onDelete={handleDelete}
          />
        </Card>
      </div>

      <AddHoldingDrawer open={drawerOpen} onClose={() => setDrawerOpen(false)} onSubmit={handleAdd} loading={submitting} />
    </PageWrapper>
  );
}
