import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Legend, CartesianGrid } from "recharts";

const tooltipStyle = {
  fontFamily: "JetBrains Mono",
  fontSize: 12,
  border: "1px solid rgba(0,0,0,0.08)",
  borderRadius: 8,
  background: "hsl(var(--card))",
};

export default function WeightsBar({ data = [] }) {
  return (
    <ResponsiveContainer width="100%" height={320}>
      <BarChart data={data} margin={{ top: 8, right: 16, left: 0, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--foreground) / 0.06)" vertical={false} />
        <XAxis
          dataKey="ticker"
          tick={{ fontSize: 10, fontFamily: "JetBrains Mono", fill: "hsl(var(--muted-foreground))" }}
          axisLine={false}
          tickLine={false}
          angle={-20}
          height={50}
          textAnchor="end"
        />
        <YAxis
          tickFormatter={(v) => `${v}%`}
          tick={{ fontSize: 10, fontFamily: "JetBrains Mono", fill: "hsl(var(--muted-foreground))" }}
          axisLine={false}
          tickLine={false}
          width={40}
        />
        <Tooltip contentStyle={tooltipStyle} formatter={(v) => `${Number(v).toFixed(1)}%`} />
        <Legend wrapperStyle={{ fontFamily: "DM Sans", fontSize: 12 }} />
        <Bar dataKey="current" fill="hsl(var(--muted-foreground) / 0.5)" name="Current" radius={[4, 4, 0, 0]} />
        <Bar dataKey="optimal" fill="hsl(var(--primary))" name="Optimal" radius={[4, 4, 0, 0]} />
      </BarChart>
    </ResponsiveContainer>
  );
}
