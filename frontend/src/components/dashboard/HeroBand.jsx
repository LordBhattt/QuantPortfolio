import Sparkline from "../ui-qp/Sparkline";
import EmptyState from "../ui-qp/EmptyState";
import { formatINR } from "../../utils/format";

export default function HeroBand({ totalValue, dayChange, dayChangePct, asOf, sparkData = [], empty, onAdd }) {
  const positive = (dayChange ?? 0) >= 0;
  const borderColor = positive ? "border-l-primary" : "border-l-gray-400";

  if (empty) {
    return (
      <div className="w-full bg-white rounded-2xl border border-black/[0.05] border-l-4 border-l-gray-300 shadow-card p-6">
        <EmptyState title="No holdings yet" subtitle="Add your first position to get started" actionLabel="+ Add Holding" onAction={onAdd} />
      </div>
    );
  }

  return (
    <div className={`relative w-full bg-white rounded-2xl border border-black/[0.05] border-l-4 ${borderColor} shadow-card overflow-hidden`}>
      <div className="flex items-stretch">
        <div className="flex-1 p-6 min-w-0">
          <div className="text-[11px] font-sans font-semibold tracking-[0.14em] uppercase text-gray-400">Portfolio Value</div>
          <div className="mt-2 text-5xl lg:text-6xl font-mono font-bold tracking-tight text-gray-900 truncate">
            {formatINR(totalValue)}
          </div>
          <div className="mt-3">
            {positive ? (
              <span className="inline-flex items-center gap-1.5 bg-gray-900 text-white font-mono text-xs px-3 py-1.5 rounded-full">
                +{formatINR(Math.abs(dayChange))} | +{Math.abs(dayChangePct).toFixed(2)}%
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 bg-red-50 text-red-700 border border-red-200 font-mono text-xs px-3 py-1.5 rounded-full">
                -{formatINR(Math.abs(dayChange))} | -{Math.abs(dayChangePct).toFixed(2)}%
              </span>
            )}
          </div>
          <div className="mt-2 text-[11px] font-mono text-gray-400">{asOf}</div>
        </div>

        <div className="hidden md:flex items-center w-[40%] pr-6">
          <div className="w-full">
            <Sparkline data={sparkData} height={60} positive={positive} />
          </div>
        </div>
      </div>
    </div>
  );
}
