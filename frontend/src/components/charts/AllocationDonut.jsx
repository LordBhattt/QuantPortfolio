import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer } from "recharts";

const COLORS = {
  stocks: "#2563EB",
  crypto: "#0891b2",
  gold: "#d97706",
  mf_etf: "#7c3aed",
  bonds: "#16a34a",
};

const tooltipStyle = {
  fontFamily: "JetBrains Mono",
  fontSize: 12,
  border: "1px solid rgba(0,0,0,0.08)",
  borderRadius: 8,
  background: "#fff",
};

export default function AllocationDonut({ data = [] }) {
  const top = [...data].sort((a, b) => b.value - a.value)[0];
  const max = Math.max(...data.map((d) => d.value), 1);

  return (
    <div className="relative">
      <ResponsiveContainer width="100%" height={220}>
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" innerRadius={62} outerRadius={92} paddingAngle={2} strokeWidth={0}>
            {data.map((entry) => (
              <Cell key={entry.key} fill={COLORS[entry.key] || "#64748b"} />
            ))}
          </Pie>
          <Tooltip contentStyle={tooltipStyle} formatter={(v) => `${Number(v).toFixed(1)}%`} />
        </PieChart>
      </ResponsiveContainer>
      <div className="absolute inset-x-0 top-0 h-[220px] flex flex-col items-center justify-center pointer-events-none">
        <div className="text-[10px] font-sans uppercase tracking-[0.12em] text-gray-400">{top?.name}</div>
        <div className="font-mono text-lg font-bold text-gray-900">{top?.value.toFixed(1)}%</div>
      </div>

      <div className="mt-4 space-y-2">
        {data.map((d) => (
          <div key={d.key} className="grid grid-cols-[12px_minmax(0,1fr)_1fr_auto] items-center gap-3 text-xs">
            <span className="w-3 h-3 rounded-sm" style={{ background: COLORS[d.key] }} />
            <span className="font-sans font-medium text-gray-900 truncate">{d.name}</span>
            <span className="h-1.5 bg-black/[0.06] rounded-full overflow-hidden">
              <span className="block h-full rounded-full" style={{ width: `${(d.value / max) * 100}%`, background: COLORS[d.key] }} />
            </span>
            <span className="font-mono text-gray-500 text-right">{d.value.toFixed(1)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
}
