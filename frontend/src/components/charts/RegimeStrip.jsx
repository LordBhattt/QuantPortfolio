const REGIME_COLORS = { bull: "#16a34a", sideways: "#9ca3af", bear: "#dc2626" };
const REGIME_LABELS = { bull: "Bull", sideways: "Sideways", bear: "Bear" };

export default function RegimeStrip({ points = [] }) {
  const segments = [];
  for (const point of points) {
    const regime = point.regime || "sideways";
    const last = segments[segments.length - 1];
    if (last && last.regime === regime) {
      last.count += 1;
    } else {
      segments.push({ regime, count: 1 });
    }
  }
  const total = points.length || 1;

  return (
    <div>
      <div className="flex h-3 w-full overflow-hidden rounded-full border border-black/[0.06]">
        {segments.map((segment, index) => (
          <div
            key={index}
            title={REGIME_LABELS[segment.regime] || segment.regime}
            style={{ width: `${(segment.count / total) * 100}%`, backgroundColor: REGIME_COLORS[segment.regime] || "#e5e7eb" }}
          />
        ))}
      </div>
      <div className="mt-2 flex items-center gap-4 text-[11px] font-mono text-gray-500">
        {Object.entries(REGIME_LABELS).map(([key, label]) => (
          <div key={key} className="flex items-center gap-1.5">
            <span className="h-2 w-2 rounded-full" style={{ backgroundColor: REGIME_COLORS[key] }} />
            {label}
          </div>
        ))}
      </div>
    </div>
  );
}
