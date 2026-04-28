import AssetClassPill, { resolveClass } from "../ui-qp/AssetClassPill";
import PnLPill from "../ui-qp/PnLPill";
import { formatINR, formatINRCompact } from "../../utils/format";

export default function RebalanceTrades({ trades = [] }) {
  if (!trades.length) return null;
  return (
    <div className="space-y-2">
      {trades.map((t) => {
        const positive = t.amount >= 0;
        return (
          <div key={t.ticker} className="flex items-center justify-between px-3 py-2.5 bg-black/[0.02] rounded-lg hover:bg-black/[0.04] transition-colors">
            <div className="flex items-center gap-3 min-w-0">
              <span
                className={`font-mono text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded ${
                  t.action === "BUY" ? "bg-gray-900 text-white" : "bg-gray-100 text-gray-700 border border-gray-200"
                }`}
              >
                {t.action}
              </span>
              <span className="font-mono text-sm font-semibold uppercase tracking-wider text-gray-900 truncate">{t.ticker}</span>
              {t.cls && <AssetClassPill cls={t.cls} />}
            </div>
            <PnLPill positive={positive}>
              {positive ? "+" : "-"}{formatINRCompact(Math.abs(t.amount))}
            </PnLPill>
          </div>
        );
      })}
    </div>
  );
}
