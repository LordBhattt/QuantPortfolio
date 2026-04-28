// Asset class pill used throughout (holdings, views, trades).
const STYLES = {
  Stock: "bg-blue-50 text-blue-700 border border-blue-200",
  Crypto: "bg-cyan-50 text-cyan-700 border border-cyan-200",
  Gold: "bg-amber-50 text-amber-700 border border-amber-200",
  "MF/ETF": "bg-violet-50 text-violet-700 border border-violet-200",
  Bond: "bg-emerald-50 text-emerald-700 border border-emerald-200",
};

const ALIASES = {
  stock: "Stock",
  Stocks: "Stock",
  bond: "Bond",
  Bonds: "Bond",
  "Mutual Funds / ETFs": "MF/ETF",
  "MF / ETF": "MF/ETF",
  mf_etf: "MF/ETF",
  stocks: "Stock",
  crypto: "Crypto",
  gold: "Gold",
  bonds: "Bond",
};

export function resolveClass(cls) {
  return ALIASES[cls] || cls;
}

export default function AssetClassPill({ cls, className = "" }) {
  const key = resolveClass(cls);
  const style = STYLES[key] || "bg-gray-100 text-gray-700 border border-gray-200";
  return (
    <span className={`inline-flex items-center font-sans text-[11px] font-medium px-2 py-0.5 rounded-full ${style} ${className}`}>
      {key}
    </span>
  );
}
