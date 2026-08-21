import { Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

export const STRATEGY_COLORS = {
  equal_weight: "#9ca3af",
  static_mvo: "#f59e0b",
  mvo_ledoit_wolf: "#3b82f6",
  full_pipeline: "hsl(var(--primary))",
  adaptive_bandit: "#a855f7",
  no_tax: "#9ca3af",
  fifo: "#f59e0b",
  tax_aware: "hsl(var(--primary))",
};

export const STRATEGY_LABELS = {
  equal_weight: "Equal Weight",
  static_mvo: "Static MVO",
  mvo_ledoit_wolf: "MVO + Ledoit-Wolf",
  full_pipeline: "BL + LW + HMM (production)",
  adaptive_bandit: "Adaptive Bandit",
  no_tax: "Frictionless (no tax)",
  fifo: "Naive FIFO",
  tax_aware: "Tax-Aware",
};

export default function BacktestEquityChart({ data = [], strategies = [] }) {
  return (
    <ResponsiveContainer width="100%" height={340}>
      <LineChart data={data} margin={{ top: 8, right: 8, left: -8, bottom: 0 }}>
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
          tickFormatter={(value) => `${Number(value).toFixed(2)}x`}
          width={48}
        />
        <Tooltip
          formatter={(value, name) => [`${Number(value).toFixed(3)}x`, STRATEGY_LABELS[name] || name]}
          labelStyle={{ fontFamily: "JetBrains Mono", fontSize: 11 }}
          contentStyle={{ borderRadius: 8, fontFamily: "JetBrains Mono", fontSize: 11 }}
        />
        <Legend wrapperStyle={{ fontSize: 11, fontFamily: "JetBrains Mono" }} formatter={(value) => STRATEGY_LABELS[value] || value} />
        {strategies.map((name) => (
          <Line
            key={name}
            type="monotone"
            dataKey={name}
            stroke={STRATEGY_COLORS[name] || "#999"}
            strokeWidth={name === "full_pipeline" ? 2.5 : 1.5}
            dot={false}
            isAnimationActive={false}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}
