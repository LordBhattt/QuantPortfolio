export default function PageWrapper({ children, title, subtitle }) {
  return (
    <div className="min-h-[calc(100vh-3.5rem)] min-w-0 overflow-x-hidden">
      <div className="max-w-[1400px] mx-auto px-4 sm:px-6 py-8 min-w-0 animate-fadeUp opacity-0" style={{ animationDelay: "0ms", animationFillMode: "forwards" }}>
        {(title || subtitle) && (
          <div className="mb-6">
            {title && <h1 className="text-2xl font-sans font-bold tracking-tight text-gray-900">{title}</h1>}
            {subtitle && <p className="mt-1 text-sm font-mono text-gray-500">{subtitle}</p>}
          </div>
        )}
        {children}
      </div>
    </div>
  );
}
