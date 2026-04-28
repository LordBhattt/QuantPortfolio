import { useEffect, useMemo, useState } from "react";

import { searchAssets } from "../../api/assets";
import AssetClassPill from "../ui-qp/AssetClassPill";

const INITIAL_FORM = {
  ticker: "",
  assetClass: "",
  quantity: "",
  avg_buy_price: "",
  buy_currency: "INR",
};

const CLASS_OPTIONS = [
  { label: "All", value: "" },
  { label: "Stock", value: "stock" },
  { label: "Crypto", value: "crypto" },
  { label: "Gold", value: "gold" },
  { label: "MF/ETF", value: "mf_etf" },
  { label: "Bond", value: "bond" },
];

export default function AddHoldingDrawer({ open, onClose, onSubmit, loading = false }) {
  const [form, setForm] = useState(INITIAL_FORM);
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [searchError, setSearchError] = useState(null);

  useEffect(() => {
    if (!open) {
      setForm(INITIAL_FORM);
      setResults([]);
      setSearchError(null);
      return;
    }

    const onEsc = (event) => event.key === "Escape" && onClose?.();
    window.addEventListener("keydown", onEsc);
    return () => window.removeEventListener("keydown", onEsc);
  }, [open, onClose]);

  useEffect(() => {
    if (!open) return undefined;

    const timer = window.setTimeout(async () => {
      const query = form.ticker.trim();
      if (!query) {
        setResults([]);
        setSearchError(null);
        return;
      }

      setSearching(true);
      try {
        const data = await searchAssets(query, form.assetClass || undefined);
        setResults(Array.isArray(data) ? data : []);
        setSearchError(null);
      } catch (err) {
        setResults([]);
        setSearchError(err.response?.data?.detail || "Asset search is unavailable. Manual ticker entry still works.");
      } finally {
        setSearching(false);
      }
    }, 300);

    return () => window.clearTimeout(timer);
  }, [form.assetClass, form.ticker, open]);

  const canSubmit = useMemo(() => {
    return Boolean(form.ticker.trim()) && Number(form.quantity) > 0 && Number(form.avg_buy_price) > 0 && !loading;
  }, [form, loading]);

  if (!open) return null;

  const selectAsset = (asset) => {
    setForm((prev) => ({
      ...prev,
      ticker: asset.ticker,
      assetClass: asset.asset_class || prev.assetClass,
      buy_currency: asset.currency || prev.buy_currency,
    }));
    setResults([]);
  };

  const submit = async (event) => {
    event.preventDefault();
    if (!canSubmit) return;

    await onSubmit?.({
      ticker: form.ticker.trim().toUpperCase(),
      quantity: Number(form.quantity),
      avg_buy_price: Number(form.avg_buy_price),
      buy_currency: form.buy_currency,
    });
  };

  return (
    <>
      <div className="fixed inset-0 top-14 bg-foreground/20 backdrop-blur-[2px] z-40 animate-fadeUp" onClick={onClose} />
      <aside className="fixed right-0 top-14 bottom-0 w-96 bg-card border-l border-black/[0.08] shadow-card-hover z-50 animate-slide-in-right overflow-y-auto">
        <div className="p-6 border-b border-black/[0.06] flex items-center justify-between">
          <h3 className="text-sm font-sans font-semibold text-foreground">Add Holding</h3>
          <button onClick={onClose} className="text-gray-400 hover:text-gray-900 transition-colors" aria-label="Close" disabled={loading}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M6 6l12 12M18 6L6 18" /></svg>
          </button>
        </div>

        <form onSubmit={submit} className="p-6 space-y-5">
          <Field label="Asset Search">
            <input
              value={form.ticker}
              onChange={(event) => setForm((prev) => ({ ...prev, ticker: event.target.value.toUpperCase() }))}
              placeholder="RELIANCE.NS or BTC"
              className="w-full px-3 py-2 text-sm font-mono border border-black/[0.1] rounded-lg outline-none focus:border-primary transition-colors"
              required
            />
            <p className="mt-2 text-xs font-mono text-gray-400">Search supported assets. You can also type a ticker manually.</p>
          </Field>

          <Field label="Asset Class Filter">
            <select
              value={form.assetClass}
              onChange={(event) => setForm((prev) => ({ ...prev, assetClass: event.target.value }))}
              className="w-full px-3 py-2 text-sm font-sans border border-black/[0.1] rounded-lg outline-none focus:border-primary transition-colors bg-white"
            >
              {CLASS_OPTIONS.map((option) => (
                <option key={option.value || "all"} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </Field>

          {(searching || results.length > 0 || searchError) && (
            <div className="rounded-xl border border-black/[0.06] bg-black/[0.02] overflow-hidden">
              {searching && <div className="px-3 py-2 text-xs font-mono text-gray-500">Searching assets...</div>}
              {!searching && results.length > 0 && (
                <div className="max-h-48 overflow-y-auto">
                  {results.map((asset) => (
                    <button
                      type="button"
                      key={asset.ticker}
                      onClick={() => selectAsset(asset)}
                      className="w-full px-3 py-2.5 text-left hover:bg-black/[0.04] transition-colors border-b border-black/[0.04] last:border-0"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0">
                          <div className="font-mono text-sm font-semibold text-gray-900 truncate">{asset.ticker}</div>
                          <div className="text-xs font-sans text-gray-500 truncate">{asset.name}</div>
                        </div>
                        <AssetClassPill cls={asset.asset_class} className="shrink-0" />
                      </div>
                    </button>
                  ))}
                </div>
              )}
              {!searching && searchError && <div className="px-3 py-2 text-xs font-mono text-amber-700">{searchError}</div>}
            </div>
          )}

          <Field label="Quantity">
            <input
              type="number"
              step="any"
              min="0"
              value={form.quantity}
              onChange={(event) => setForm((prev) => ({ ...prev, quantity: event.target.value }))}
              className="w-full px-3 py-2 text-sm font-mono border border-black/[0.1] rounded-lg outline-none focus:border-primary transition-colors"
              required
            />
          </Field>

          <Field label="Average Buy Price">
            <input
              type="number"
              step="any"
              min="0"
              value={form.avg_buy_price}
              onChange={(event) => setForm((prev) => ({ ...prev, avg_buy_price: event.target.value }))}
              className="w-full px-3 py-2 text-sm font-mono border border-black/[0.1] rounded-lg outline-none focus:border-primary transition-colors"
              required
            />
          </Field>

          <Field label="Buy Currency">
            <select
              value={form.buy_currency}
              onChange={(event) => setForm((prev) => ({ ...prev, buy_currency: event.target.value }))}
              className="w-full px-3 py-2 text-sm font-sans border border-black/[0.1] rounded-lg outline-none focus:border-primary transition-colors bg-white"
            >
              <option value="INR">INR</option>
              <option value="USD">USD</option>
            </select>
          </Field>

          <button
            type="submit"
            disabled={!canSubmit}
            className="w-full py-2.5 bg-primary text-primary-foreground text-sm font-sans font-semibold rounded-lg hover:bg-primary-dark transition-colors disabled:opacity-50"
          >
            {loading ? "Adding..." : "Add Holding"}
          </button>
        </form>
      </aside>
    </>
  );
}

function Field({ label, children }) {
  return (
    <div>
      <label className="block text-[11px] font-sans font-medium tracking-[0.12em] uppercase text-muted-foreground mb-2">
        {label}
      </label>
      {children}
    </div>
  );
}
