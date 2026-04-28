import { useState } from "react";
import AssetClassPill from "../ui-qp/AssetClassPill";

function ConfidenceDots({ value }) {
  // value 0..1; render 5 dots
  const filled = Math.max(1, Math.min(5, Math.round(value * 5)));
  return (
    <div className="flex items-center gap-1">
      {[1, 2, 3, 4, 5].map((i) => (
        <span
          key={i}
          className={`w-1.5 h-1.5 rounded-full ${i <= filled ? "bg-gray-900" : "bg-gray-200"}`}
        />
      ))}
    </div>
  );
}

function XIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
      <path d="M6 6l12 12M18 6L6 18" />
    </svg>
  );
}

const CLASS_BY_TICKER = {
  AAPL: "Stock",
  MSFT: "Stock",
  "RELIANCE.NS": "Stock",
  "TCS.NS": "Stock",
  BTC: "Crypto",
  ETH: "Crypto",
  GLDBEES: "Gold",
  NIFTYBEES: "MF/ETF",
  LIQUIDBEES: "Bond",
};

export default function UserViewsPanel({ views, onChange }) {
  const [ticker, setTicker] = useState("");
  const [expected, setExpected] = useState("");
  const [confidence, setConfidence] = useState(50);

  const add = () => {
    if (!ticker || !expected) return;
    onChange([...views, { ticker: ticker.toUpperCase(), expected: parseFloat(expected) / 100, confidence: confidence / 100 }]);
    setTicker("");
    setExpected("");
    setConfidence(50);
  };

  const remove = (i) => onChange(views.filter((_, idx) => idx !== i));

  return (
    <div>
      <div className="text-[11px] font-sans font-semibold tracking-[0.14em] uppercase text-gray-400 mb-3">
        User Views (Black-Litterman)
      </div>

      {views.length > 0 && (
        <div className="space-y-2 mb-3">
          {views.map((v, i) => {
            const cls = CLASS_BY_TICKER[v.ticker] || "Stock";
            return (
              <div key={i} className="grid grid-cols-[auto_1fr_auto_auto] items-center gap-3 px-3 py-2 bg-black/[0.02] rounded-lg">
                <AssetClassPill cls={cls} />
                <span className="font-mono text-sm font-semibold uppercase tracking-wider text-gray-900 truncate">{v.ticker}</span>
                <span className="font-mono text-lg font-bold text-gray-900">
                  {v.expected >= 0 ? "+" : ""}{(v.expected * 100).toFixed(1)}%
                </span>
                <ConfidenceDots value={v.confidence} />
                <button onClick={() => remove(i)} className="text-gray-400 hover:text-gray-900 transition-colors col-start-5" aria-label="Remove">
                  <XIcon />
                </button>
              </div>
            );
          })}
        </div>
      )}

      <div className="grid grid-cols-[1fr_80px_80px_auto] gap-2">
        <input
          value={ticker}
          onChange={(e) => setTicker(e.target.value)}
          placeholder="AAPL"
          className="px-2 py-1.5 text-xs font-mono uppercase border border-black/[0.1] rounded-md outline-none focus:border-primary"
        />
        <input
          value={expected}
          onChange={(e) => setExpected(e.target.value)}
          placeholder="+5%"
          className="px-2 py-1.5 text-xs font-mono border border-black/[0.1] rounded-md outline-none focus:border-primary"
        />
        <input
          type="number"
          value={confidence}
          onChange={(e) => setConfidence(e.target.value)}
          placeholder="conf"
          className="px-2 py-1.5 text-xs font-mono border border-black/[0.1] rounded-md outline-none focus:border-primary"
        />
        <button
          onClick={add}
          className="px-3 py-1.5 text-xs font-sans font-semibold bg-gray-900 text-white rounded-md hover:opacity-90 transition-opacity"
        >
          +
        </button>
      </div>
    </div>
  );
}
