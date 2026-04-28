// Black/ghost pill system for gains / losses.
export default function PnLPill({ positive, children, size = "sm", className = "" }) {
  const pad = size === "lg" ? "px-3 py-1.5 text-sm" : "px-2.5 py-1 text-xs";
  const style = positive
    ? "bg-gray-900 text-white"
    : "bg-gray-100 text-gray-600 border border-gray-200";
  return (
    <span className={`inline-flex items-center gap-1 font-mono rounded-full ${pad} ${style} ${className}`}>
      {children}
    </span>
  );
}
