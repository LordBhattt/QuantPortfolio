import { Area, CartesianGrid, ComposedChart, Line, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { formatINR } from "../../utils/format";

function MCTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  const pick = (key) => payload.find((item) => item.dataKey === key)?.value;

  return (
    <div className="bg-white rounded-lg shadow-card p-3 font-mono text-xs">
      <div className="text-[10px] text-gray-400 mb-1.5">Day {label}</div>
      {["p95", "p75", "p50", "p25", "p5"].map((key) => {
        const value = pick(key);
        if (value === undefined) return null;
        return (
          <div key={key} className="flex justify-between gap-4">
            <span className="text-gray-500 uppercase">{key}</span>
            <span className="text-gray-900">{formatINR(value)}</span>
          </div>
        );
      })}
    </div>
  );
}

export default function MonteCarloChart({ data = {}, showToday = true }) {
  const chartData = (data.p50 || []).map((_, index) => ({
    day: index,
    p5: data.p5?.[index],
    p25: data.p25?.[index],
    p50: data.p50?.[index],
    p75: data.p75?.[index],
    p95: data.p95?.[index],
    band95: [data.p5?.[index], data.p95?.[index]],
    band50: [data.p25?.[index], data.p75?.[index]],
  }));

  return (
    <div className="relative">
      <ResponsiveContainer width="100%" height={380}>
        <ComposedChart data={chartData} margin={{ top: 8, right: 56, left: -8, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--foreground) / 0.06)" />
          <XAxis
            dataKey="day"
            tick={{ fontSize: 10, fontFamily: "JetBrains Mono", fill: "hsl(var(--muted-foreground))" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tick={{ fontSize: 10, fontFamily: "JetBrains Mono", fill: "hsl(var(--muted-foreground))" }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(value) => `\u20B9${(value / 10000000).toFixed(1)}Cr`}
            width={64}
          />
          <Tooltip content={<MCTooltip />} />
          {showToday && (
            <ReferenceLine
              x={0}
              stroke="hsl(var(--foreground))"
              strokeDasharray="4 4"
              label={{ value: "Today", position: "insideTopLeft", fontSize: 10, fontFamily: "JetBrains Mono", fill: "hsl(var(--foreground))" }}
            />
          )}
          <Area dataKey="band95" stroke="none" fill="hsl(var(--primary))" fillOpacity={0.08} name="5-95%" />
          <Area dataKey="band50" stroke="none" fill="hsl(var(--primary))" fillOpacity={0.18} name="25-75%" />
          <Line type="monotone" dataKey="p50" stroke="hsl(var(--primary))" strokeWidth={2} dot={false} name="Median" />
        </ComposedChart>
      </ResponsiveContainer>

      <div className="absolute right-2 top-2 bottom-6 pointer-events-none hidden md:flex flex-col justify-between text-right">
        {["95th", "75th", "Median", "25th", "5th"].map((label) => (
          <span key={label} className="text-[10px] font-mono text-gray-400">{label}</span>
        ))}
      </div>
    </div>
  );
}
