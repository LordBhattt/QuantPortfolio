import { Fragment, useState } from "react";

import EmptyState from "../ui-qp/EmptyState";
import AssetClassPill from "../ui-qp/AssetClassPill";
import PnLPill from "../ui-qp/PnLPill";
import Sparkline from "../ui-qp/Sparkline";
import { formatINR, formatINRCompact } from "../../utils/format";

export default function HoldingsTable({ holdings = [], onAdd, onDelete, loading = false }) {
  const [expanded, setExpanded] = useState(null);

  if (loading) {
    return (
      <div className="space-y-3">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="grid grid-cols-5 gap-3 py-3 border-b border-black/[0.04]">
            {Array.from({ length: 5 }).map((__, cellIndex) => (
              <div key={cellIndex} className="h-5 rounded bg-gray-100 animate-pulse" />
            ))}
          </div>
        ))}
      </div>
    );
  }

  if (!holdings.length) {
    return (
      <EmptyState
        title="No holdings yet"
        subtitle="Add your first position to get started"
        actionLabel={onAdd ? "+ Add Holding" : undefined}
        onAction={onAdd}
      />
    );
  }

  return (
    <div className="w-full">
      <table className="w-full text-sm table-fixed">
        <colgroup>
          <col className="w-[26%]" />
          <col className="w-[14%]" />
          <col className="w-[18%]" />
          <col className="w-[18%]" />
          <col className="w-[24%]" />
        </colgroup>
        <thead>
          <tr className="border-b border-black/[0.08]">
            {["Ticker", "Class", "Value", "P&L", "Weight"].map((heading) => (
              <th key={heading} className="text-left py-2.5 px-3 text-[11px] font-sans font-semibold tracking-[0.14em] uppercase text-gray-400">
                {heading}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {holdings.map((holding) => {
            const value = Number(holding.current || 0) * Number(holding.qty || 0);
            const pnlPct = Number(holding.pnlPct || 0);
            const weight = Number(holding.weight || 0);
            const positive = Number(holding.pnl || 0) >= 0;
            const isOpen = expanded === holding.id;
            const spark = holding.spark?.length ? holding.spark : Array.from({ length: 7 }, () => Number(holding.current || 0));

            return (
              <Fragment key={holding.id || holding.ticker}>
                <tr
                  onClick={() => setExpanded(isOpen ? null : holding.id)}
                  className="border-b border-black/[0.04] hover:bg-black/[0.02] transition-colors cursor-pointer"
                >
                  <td className="py-3 px-3">
                    <div className="flex flex-col">
                      <span className="font-mono font-semibold uppercase tracking-wider text-gray-900">{holding.ticker}</span>
                      {holding.name && <span className="text-[11px] text-gray-400 font-sans truncate">{holding.name}</span>}
                    </div>
                  </td>
                  <td className="py-3 px-3"><AssetClassPill cls={holding.cls} /></td>
                  <td className="py-3 px-3 font-mono text-gray-900">{formatINRCompact(value)}</td>
                  <td className="py-3 px-3">
                    <PnLPill positive={positive}>
                      {pnlPct >= 0 ? "+" : ""}{pnlPct.toFixed(2)}%
                    </PnLPill>
                  </td>
                  <td className="py-3 px-3">
                    <div className="flex items-center gap-2">
                      <div className="flex-1 h-2 bg-black/[0.06] rounded-full overflow-hidden">
                        <div className="h-full bg-primary rounded-full" style={{ width: `${Math.min(100, Math.max(0, weight))}%` }} />
                      </div>
                      <span className="font-mono text-xs text-gray-500 shrink-0">{weight.toFixed(1)}%</span>
                    </div>
                  </td>
                </tr>
                <tr>
                  <td colSpan={5} className="p-0">
                    <div
                      className="overflow-hidden transition-[max-height,opacity] duration-300 ease-out"
                      style={{ maxHeight: isOpen ? 180 : 0, opacity: isOpen ? 1 : 0 }}
                    >
                      <div className="grid grid-cols-[repeat(3,minmax(0,1fr))_180px] gap-6 py-4 px-4 bg-black/[0.02] border-b border-black/[0.04]">
                        <Detail label="Avg Buy" value={formatINR(holding.avg)} />
                        <Detail label="Current" value={formatINR(holding.current)} />
                        <Detail label="Quantity" value={Number(holding.qty || 0).toLocaleString("en-IN")} />
                        <div>
                          <div className="text-[10px] font-sans font-semibold tracking-[0.14em] uppercase text-gray-400 mb-1">7-Day</div>
                          <div className="h-10">
                            <Sparkline data={spark} height={40} positive={positive} />
                          </div>
                        </div>
                      </div>
                      {onDelete && (
                        <div className="px-4 pb-4 bg-black/[0.02] border-b border-black/[0.04]">
                          <button
                            onClick={(event) => {
                              event.stopPropagation();
                              onDelete(holding);
                            }}
                            className="px-3 py-2 text-xs font-sans font-semibold rounded-lg border border-red-200 text-red-700 hover:bg-red-50 transition-colors"
                          >
                            Remove Holding
                          </button>
                        </div>
                      )}
                    </div>
                  </td>
                </tr>
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function Detail({ label, value }) {
  return (
    <div>
      <div className="text-[10px] font-sans font-semibold tracking-[0.14em] uppercase text-gray-400">{label}</div>
      <div className="mt-1 font-mono text-sm text-gray-900">{value}</div>
    </div>
  );
}
