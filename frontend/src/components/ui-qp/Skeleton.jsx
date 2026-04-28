export function SkeletonStat() {
  return (
    <div className="p-5 bg-card rounded-xl border border-black/[0.08] shadow-card">
      <div className="h-3 w-20 bg-gray-100 rounded animate-pulse" />
      <div className="mt-3 h-8 w-32 bg-gray-100 rounded animate-pulse" />
      <div className="mt-2 h-3 w-24 bg-gray-100 rounded animate-pulse" />
    </div>
  );
}

export function SkeletonRow({ cols = 5 }) {
  return (
    <div className="flex gap-3 py-3 border-b border-black/[0.04]">
      {Array.from({ length: cols }).map((_, i) => (
        <div key={i} className="h-4 flex-1 bg-gray-100 rounded animate-pulse" />
      ))}
    </div>
  );
}

export function SkeletonChart({ height = "h-64" }) {
  return <div className={`${height} w-full bg-gray-50 rounded-xl animate-pulse`} />;
}
