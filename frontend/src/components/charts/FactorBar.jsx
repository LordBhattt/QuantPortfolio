import { BarChart, Bar, XAxis, YAxis, Tooltip, ReferenceLine, ResponsiveContainer, Cell, CartesianGrid } from "recharts";

const tooltipStyle = {
  fontFamily: "JetBrains Mono",
  fontSize: 12,
  border: "1px solid rgba(0,0,0,0.08)",
  borderRadius: 8,
  background: "hsl(var(--card))",
};

export default function FactorBar({ data = [] }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} margin={{ top: 16, right: 16, left: 0, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--foreground) / 0.06)" vertical={false} />
        <XAxis
          dataKey="factor"
          tick={{ fontSize: 11, fontFamily: "JetBrains Mono", fill: "hsl(var(--muted-foreground))" }}
          axisLine={false}
          tickLine={false}
        />
        <YAxis
          tickFormatter={(v) => `${(v * 100).toFixed(0)}%`}
          tick={{ fontSize: 10, fontFamily: "JetBrains Mono", fill: "hsl(var(--muted-foreground))" }}
          axisLine={false}
          tickLine={false}
          width={48}
        />
        <Tooltip contentStyle={tooltipStyle} formatter={(v) => `${(v * 100).toFixed(1)}%`} />
        <ReferenceLine y={0} stroke="hsl(var(--foreground) / 0.2)" />
        <Bar dataKey="exposure" radius={[4, 4, 0, 0]}>
          {data.map((entry, i) => (
            <Cell key={i} fill={entry.exposure >= 0 ? "hsl(var(--primary))" : "hsl(var(--destructive))"} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
