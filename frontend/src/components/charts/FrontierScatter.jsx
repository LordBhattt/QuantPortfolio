import { CartesianGrid, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis, ZAxis } from "recharts";

const tooltipStyle = {
  fontFamily: "JetBrains Mono",
  fontSize: 12,
  border: "1px solid rgba(0,0,0,0.08)",
  borderRadius: 8,
  background: "hsl(var(--card))",
};

export default function FrontierScatter({ data = [], optimal }) {
  return (
    <ResponsiveContainer width="100%" height={360}>
      <ScatterChart margin={{ top: 16, right: 16, left: 0, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="hsl(var(--foreground) / 0.06)" />
        <XAxis
          type="number"
          dataKey="risk"
          name="Risk"
          tickFormatter={(value) => `${(value * 100).toFixed(1)}%`}
          tick={{ fontSize: 10, fontFamily: "JetBrains Mono", fill: "hsl(var(--muted-foreground))" }}
          axisLine={false}
          tickLine={false}
          domain={["auto", "auto"]}
          label={{ value: "Risk (sigma)", position: "insideBottom", offset: -4, fontSize: 10, fontFamily: "DM Sans", fill: "hsl(var(--muted-foreground))" }}
        />
        <YAxis
          type="number"
          dataKey="return"
          name="Return"
          tickFormatter={(value) => `${(value * 100).toFixed(1)}%`}
          tick={{ fontSize: 10, fontFamily: "JetBrains Mono", fill: "hsl(var(--muted-foreground))" }}
          axisLine={false}
          tickLine={false}
          width={48}
        />
        <ZAxis range={[40, 40]} />
        <Tooltip
          cursor={{ strokeDasharray: "3 3" }}
          contentStyle={tooltipStyle}
          formatter={(value) => `${(Number(value) * 100).toFixed(2)}%`}
        />
        <Scatter data={data} fill="hsl(var(--primary) / 0.45)" />
        {optimal && <Scatter data={[optimal]} fill="hsl(var(--primary))" shape="star" />}
      </ScatterChart>
    </ResponsiveContainer>
  );
}
