import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

function formatPercent(value) {
  const pct = Number(value || 0) * 100;
  const sign = pct >= 0 ? "+" : "";
  return `${sign}${pct.toFixed(1)}%`;
}

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;

  const portfolio = payload.find((item) => item.dataKey === "portfolio")?.value;
  const nifty50 = payload.find((item) => item.dataKey === "nifty50")?.value;
  const sp500 = payload.find((item) => item.dataKey === "sp500")?.value;

  return (
    <div className="bg-white rounded-lg shadow-card p-3 font-mono">
      <div className="text-[10px] text-gray-400 mb-1.5">{label}</div>
      {portfolio !== undefined && (
        <div className="flex items-center justify-between gap-4 text-xs">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-primary" />
            <span className="text-gray-500">Portfolio</span>
          </div>
          <span className="text-gray-900">{formatPercent(portfolio)}</span>
        </div>
      )}
      {nifty50 !== undefined && (
        <div className="flex items-center justify-between gap-4 text-xs mt-1">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-amber-500" />
            <span className="text-gray-500">NIFTY 50</span>
          </div>
          <span className="text-gray-900">{formatPercent(nifty50)}</span>
        </div>
      )}
      {sp500 !== undefined && (
        <div className="flex items-center justify-between gap-4 text-xs mt-1">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-slate-500" />
            <span className="text-gray-500">S&P 500</span>
          </div>
          <span className="text-gray-900">{formatPercent(sp500)}</span>
        </div>
      )}
    </div>
  );
}

export default function BenchmarkComparisonChart({ data = [] }) {
  return (
    <ResponsiveContainer width="100%" height={320}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
        <defs>
          <linearGradient id="benchmarkPortfolioFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.18} />
            <stop offset="55%" stopColor="hsl(var(--primary))" stopOpacity={0} />
          </linearGradient>
        </defs>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--foreground) / 0.06)" vertical={false} />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 10, fontFamily: "JetBrains Mono", fill: "hsl(var(--muted-foreground))" }}
          axisLine={false}
          tickLine={false}
          minTickGap={32}
        />
        <YAxis
          tick={{ fontSize: 10, fontFamily: "JetBrains Mono", fill: "hsl(var(--muted-foreground))" }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(value) => formatPercent(value)}
          width={64}
        />
        <Tooltip content={<CustomTooltip />} />
        <ReferenceLine y={0} stroke="hsl(var(--foreground) / 0.18)" strokeDasharray="4 4" />
        <Area type="monotone" dataKey="portfolio" stroke="hsl(var(--primary))" strokeWidth={2} fill="url(#benchmarkPortfolioFill)" />
        <Line type="monotone" dataKey="nifty50" stroke="#f59e0b" strokeWidth={2} dot={false} />
        <Line type="monotone" dataKey="sp500" stroke="#64748b" strokeWidth={2} strokeDasharray="5 4" dot={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}