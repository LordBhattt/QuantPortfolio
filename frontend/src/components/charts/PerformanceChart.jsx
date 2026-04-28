import { Area, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { formatINR } from "../../utils/format";

function CustomTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const portfolio = payload.find((item) => item.dataKey === "portfolio")?.value;
  const benchmark = payload.find((item) => item.dataKey === "benchmark")?.value;

  return (
    <div className="bg-white rounded-lg shadow-card p-3 font-mono">
      <div className="text-[10px] text-gray-400 mb-1.5">{label}</div>
      {portfolio !== undefined && (
        <div className="flex items-center justify-between gap-4 text-xs">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-primary" />
            <span className="text-gray-500">Portfolio</span>
          </div>
          <span className="text-gray-900">{formatINR(portfolio)}</span>
        </div>
      )}
      {benchmark !== undefined && (
        <div className="flex items-center justify-between gap-4 text-xs mt-1">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-gray-400" />
            <span className="text-gray-500">Benchmark</span>
          </div>
          <span className="text-gray-900">{formatINR(benchmark)}</span>
        </div>
      )}
    </div>
  );
}

export default function PerformanceChart({ data = [], costBasis }) {
  return (
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
        <defs>
          <linearGradient id="perfFill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.2} />
            <stop offset="50%" stopColor="hsl(var(--primary))" stopOpacity={0} />
          </linearGradient>
        </defs>
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
          tickFormatter={(value) => `\u20B9${(value / 100000).toFixed(0)}L`}
          width={56}
        />
        <Tooltip content={<CustomTooltip />} />
        {costBasis !== undefined && (
          <ReferenceLine
            y={costBasis}
            stroke="hsl(var(--foreground) / 0.3)"
            strokeDasharray="4 4"
            label={{ value: "Cost Basis", position: "insideTopRight", fontSize: 10, fontFamily: "JetBrains Mono", fill: "hsl(var(--muted-foreground))" }}
          />
        )}
        <Area type="monotone" dataKey="portfolio" stroke="hsl(var(--primary))" strokeWidth={2} fill="url(#perfFill)" />
        <Line type="monotone" dataKey="benchmark" stroke="hsl(var(--muted-foreground))" strokeWidth={1.5} strokeDasharray="4 4" dot={false} />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
