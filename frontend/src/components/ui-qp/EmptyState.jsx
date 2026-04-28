export default function EmptyState({ title = "Nothing here yet", subtitle, actionLabel, onAction }) {
  return (
    <div className="py-12 flex flex-col items-center justify-center text-center">
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" className="stroke-gray-300 mb-3" strokeWidth="1.5">
        <rect x="3" y="3" width="18" height="18" rx="2" />
        <path d="M3 9h18M9 3v18" />
      </svg>
      <div className="text-sm font-sans font-semibold text-gray-400">{title}</div>
      {subtitle && <div className="mt-1 text-xs font-sans text-gray-300">{subtitle}</div>}
      {actionLabel && (
        <button
          onClick={onAction}
          className="mt-4 border border-black/[0.1] text-sm font-sans font-medium px-4 py-2 rounded-lg hover:bg-black/[0.03] transition-colors"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}
