// Minimal dependency-free SVG sparkline.
export default function Sparkline({ data = [], width = 240, height = 60, positive = true }) {
  if (!data.length) return null;
  const values = data.map((d) => (typeof d === "number" ? d : d.value ?? d.portfolio ?? 0));
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const step = values.length > 1 ? width / (values.length - 1) : 0;
  const points = values.map((v, i) => {
    const x = i * step;
    const y = height - ((v - min) / range) * height;
    return [x, y];
  });
  const d = points.map(([x, y], i) => `${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`).join(" ");
  const areaD = `${d} L${width},${height} L0,${height} Z`;
  const stroke = positive ? "hsl(var(--primary))" : "hsl(215 16% 47%)";
  const gradId = `spark-${positive ? "p" : "n"}-${Math.round(values[0] * 1000) % 10000}`;

  return (
    <svg viewBox={`0 0 ${width} ${height}`} width="100%" height={height} preserveAspectRatio="none">
      <defs>
        <linearGradient id={gradId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity="0.22" />
          <stop offset="100%" stopColor={stroke} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={areaD} fill={`url(#${gradId})`} />
      <path d={d} fill="none" stroke={stroke} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}
