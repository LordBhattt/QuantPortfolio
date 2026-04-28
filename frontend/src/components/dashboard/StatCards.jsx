import Card from "../ui-qp/Card";
import { formatINRCompact, formatINR } from "../../utils/format";
import Badge from "../ui-qp/Badge";

export function InvestedVsCurrentCard({ invested, current }) {
  const safeInvested = invested > 0 ? invested : current || 1;
  const ratio = Math.min(1.5, current / safeInvested);
  const pct = Math.min(150, ratio * 100);
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="text-[11px] font-sans font-semibold tracking-[0.14em] uppercase text-gray-400">Invested</div>
          <div className="mt-1 font-mono text-sm text-gray-500">{formatINR(invested)}</div>
        </div>
        <div className="text-right">
          <div className="text-[11px] font-sans font-semibold tracking-[0.14em] uppercase text-gray-400">Current</div>
          <div className="mt-1 font-mono text-lg font-bold text-gray-900">{formatINR(current)}</div>
        </div>
      </div>
      <div className="mt-5 relative h-2 bg-gray-100 rounded-full overflow-hidden">
        <div className="absolute inset-y-0 left-0 bg-primary rounded-full" style={{ width: `${Math.min(100, pct)}%` }} />
        {pct > 100 && (
          <div className="absolute inset-y-0 left-[100%] bg-primary-dark rounded-r-full" style={{ width: `${pct - 100}%`, marginLeft: 0 }} />
        )}
      </div>
      <div className="mt-2 flex justify-between text-[10px] font-mono text-gray-400">
        <span>0</span>
        <span>{((current / safeInvested) * 100).toFixed(1)}%</span>
      </div>
    </Card>
  );
}

export function TotalReturnCard({ returnPct, absoluteGain, xirr }) {
  return (
    <Card className="p-5 relative overflow-hidden">
      {/* Watermark trend line */}
      <svg className="absolute inset-0 w-full h-full opacity-[0.06] pointer-events-none" viewBox="0 0 200 100" preserveAspectRatio="none">
        <path d="M0,85 L40,70 L80,60 L120,40 L160,25 L200,10" stroke="currentColor" strokeWidth="2" fill="none" />
      </svg>
      <div className="relative">
        <div className="text-[11px] font-sans font-semibold tracking-[0.14em] uppercase text-gray-400">Total Return</div>
        <div className="mt-2 font-mono text-4xl font-bold tracking-tight text-gray-900">
          {returnPct >= 0 ? "+" : ""}{returnPct.toFixed(1)}%
        </div>
        <div className="mt-2 font-mono text-xs text-gray-500">
          {absoluteGain >= 0 ? "+" : ""}{formatINR(absoluteGain)} absolute gain
        </div>
        <div className="mt-3 font-mono text-xs text-gray-900">
          <span className="text-gray-400">XIRR</span>&nbsp;&nbsp;{xirr.toFixed(1)}% p.a.
        </div>
      </div>
    </Card>
  );
}

export function RiskSnapshotCard({ sharpe, maxDD, beta, regime }) {
  return (
    <Card className="p-5">
      <div className="flex items-start justify-between gap-4">
        <div className="space-y-2.5">
          <Metric label="SHARPE" value={sharpe.toFixed(2)} />
          <Metric label="MAX DD" value={`${maxDD.toFixed(1)}%`} />
          <Metric label="BETA" value={beta.toFixed(2)} />
        </div>
        <div className="self-center">
          <Badge regime={regime} />
        </div>
      </div>
    </Card>
  );
}

function Metric({ label, value }) {
  return (
    <div className="flex items-baseline justify-between gap-4">
      <span className="text-[10px] font-sans font-semibold tracking-[0.14em] uppercase text-gray-400">{label}</span>
      <span className="font-mono text-sm font-bold text-gray-900">{value}</span>
    </div>
  );
}
