import { Area, ComposedChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export default function BacktestDrawdownChart({ data = [], strategyKey = "full_pipeline" }) {
  return (
    <ResponsiveContainer width="100%" height={160}>
      <ComposedChart data={data} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
        <XAxis
          dataKey="date"
          tick={{ fontSize: 10, fontFamily: "JetBrains Mono", fill: "hsl(var(--muted-foreground))" }}
          axisLine={false}
          tickLine={false}
          minTickGap={48}
        />
        <YAxis
          tick={{ fontSize: 10, fontFamily: "JetBrains Mono", fill: "hsl(var(--muted-foreground))" }}
          axisLine={false}
          tickLine={false}
          tickFormatter={(value) => `${(value * 100).toFixed(0)}%`}
          width={48}
        />
        <Tooltip
          formatter={(value) => [`${(Number(value) * 100).toFixed(2)}%`, "Drawdown"]}
          labelStyle={{ fontFamily: "JetBrains Mono", fontSize: 11 }}
          contentStyle={{ borderRadius: 8, fontFamily: "JetBrains Mono", fontSize: 11 }}
        />
        <Area
          type="monotone"
          dataKey={strategyKey}
          stroke="#ef4444"
          fill="#ef4444"
          fillOpacity={0.15}
          strokeWidth={1.5}
          isAnimationActive={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
