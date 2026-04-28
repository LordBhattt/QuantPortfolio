import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import { createPortfolio } from "../../api/portfolios";
import { usePortfolios } from "../../hooks/usePortfolio";
import { usePortfolioStore } from "../../store/portfolioStore";

const ASSETS = [
  { key: "stocks", name: "Stocks", desc: "Indian + US equities" },
  { key: "crypto", name: "Crypto", desc: "Digital assets, higher variance" },
  { key: "gold", name: "Gold / Commodities", desc: "Inflation hedge" },
  { key: "mf_etf", name: "Mutual Funds / ETFs", desc: "Diversified passive exposure" },
  { key: "bonds", name: "Bonds", desc: "Fixed income, low volatility" },
];

const RISK_PROFILES = {
  conservative: {
    risk_tolerance_default: 0.25,
    constraints: {
      stocks: { min: 0.0, max: 0.6 },
      crypto: { min: 0.0, max: 0.1 },
      gold: { min: 0.05, max: 0.3 },
      mf_etf: { min: 0.0, max: 0.5 },
      bonds: { min: 0.1, max: 0.5 },
    },
  },
  balanced: {
    risk_tolerance_default: 0.5,
    constraints: {
      stocks: { min: 0.0, max: 0.8 },
      crypto: { min: 0.0, max: 0.2 },
      gold: { min: 0.0, max: 0.2 },
      mf_etf: { min: 0.0, max: 0.6 },
      bonds: { min: 0.0, max: 0.3 },
    },
  },
  aggressive: {
    risk_tolerance_default: 0.8,
    constraints: {
      stocks: { min: 0.0, max: 1.0 },
      crypto: { min: 0.0, max: 0.4 },
      gold: { min: 0.0, max: 0.15 },
      mf_etf: { min: 0.0, max: 0.6 },
      bonds: { min: 0.0, max: 0.1 },
    },
  },
};

const RISK_OPTIONS = [
  { key: "conservative", name: "Conservative", desc: "Capital preservation, lower volatility" },
  { key: "balanced", name: "Balanced", desc: "Growth with managed risk" },
  { key: "aggressive", name: "Aggressive", desc: "Maximum returns, higher variance" },
];

function Icon({ k }) {
  const props = { width: 20, height: 20, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 1.5 };
  if (k === "stocks") return <svg {...props}><path d="M3 20h18M5 16l4-6 4 4 6-10" /></svg>;
  if (k === "crypto") return <svg {...props}><circle cx="12" cy="12" r="9" /><path d="M9 8h5a2 2 0 010 4H9m0 0h6a2 2 0 010 4H9m2-10v12" /></svg>;
  if (k === "gold") return <svg {...props}><rect x="4" y="8" width="16" height="10" rx="1" /><path d="M8 8v-2h8v2" /></svg>;
  if (k === "mf_etf") return <svg {...props}><rect x="3" y="3" width="8" height="8" rx="1" /><rect x="13" y="3" width="8" height="8" rx="1" /><rect x="3" y="13" width="8" height="8" rx="1" /><rect x="13" y="13" width="8" height="8" rx="1" /></svg>;
  if (k === "bonds") return <svg {...props}><path d="M4 6h16v12H4z" /><path d="M4 10h16M8 6v12M16 6v12" /></svg>;
  return null;
}

export default function OnboardingModal() {
  const navigate = useNavigate();
  const token = usePortfolioStore((s) => s.token);
  const onboarded = usePortfolioStore((s) => s.onboarded);
  const completeOnboarding = usePortfolioStore((s) => s.completeOnboarding);
  const setPortfolio = usePortfolioStore((s) => s.setPortfolio);
  const { data: portfolios = [], loading: portfoliosLoading } = usePortfolios();

  const [step, setStep] = useState(0);
  const [name, setName] = useState("My Portfolio");
  const [desc, setDesc] = useState("");
  const [assets, setAssets] = useState(new Set(["stocks", "mf_etf"]));
  const [risk, setRisk] = useState("balanced");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  const riskProfile = useMemo(() => RISK_PROFILES[risk], [risk]);

  if (!token || onboarded || portfoliosLoading || portfolios.length > 0) return null;

  const toggleAsset = (key) => {
    const next = new Set(assets);
    if (next.has(key)) next.delete(key);
    else next.add(key);
    setAssets(next);
  };

  const finish = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const portfolio = await createPortfolio({
        name: name.trim() || "My Portfolio",
        description: desc.trim() || null,
        base_currency: "INR",
        constraints: riskProfile.constraints,
      });
      setPortfolio(portfolio.id, portfolio.name);
      completeOnboarding();
      navigate("/dashboard");
    } catch (err) {
      setError(err.response?.data?.detail || "Failed to create portfolio");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-6 overflow-y-auto">
      <div className="w-full max-w-xl bg-white rounded-2xl shadow-card-hover border border-black/[0.05] p-8 animate-fadeUp">
        <div className="flex items-center justify-center gap-2 mb-8">
          {[0, 1, 2].map((index) => (
            <span key={index} className={`w-2 h-2 rounded-full transition-colors ${index <= step ? "bg-gray-900" : "bg-gray-200"}`} />
          ))}
        </div>

        {step === 0 && (
          <div>
            <h2 className="text-2xl font-sans font-bold text-gray-900 tracking-tight">Name your portfolio</h2>
            <p className="mt-2 text-sm text-gray-500">A few details to get started.</p>

            <div className="mt-8 space-y-6">
              <UnderlineField label="Portfolio name" value={name} onChange={setName} />

              <div>
                <label className="block text-[11px] font-sans font-semibold tracking-[0.14em] uppercase text-gray-400 mb-2">
                  Base currency
                </label>
                <span className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-gray-100 text-gray-700 font-mono text-xs">
                  <span className="w-1.5 h-1.5 rounded-full bg-gray-400" />
                  INR (locked)
                </span>
              </div>

              <UnderlineField label="Description (optional)" value={desc} onChange={setDesc} small />
            </div>

            <div className="mt-10 flex justify-end">
              <PrimaryButton onClick={() => setStep(1)} disabled={!name.trim()}>
                Continue
              </PrimaryButton>
            </div>
          </div>
        )}

        {step === 1 && (
          <div>
            <h2 className="text-2xl font-sans font-bold text-gray-900 tracking-tight">What do you want to invest in?</h2>
            <p className="mt-2 text-sm text-gray-500">Pick one or more. You can change these later.</p>

            <div className="mt-6 grid grid-cols-2 gap-3">
              {ASSETS.map((asset) => {
                const selected = assets.has(asset.key);
                return (
                  <button
                    key={asset.key}
                    onClick={() => toggleAsset(asset.key)}
                    className={`text-left p-4 rounded-xl border transition-all ${
                      selected
                        ? "border-l-4 border-l-gray-900 border-r border-t border-b border-black/[0.06] bg-black/[0.03]"
                        : "border border-black/[0.08] hover:bg-black/[0.02]"
                    }`}
                  >
                    <div className="text-gray-900 mb-2"><Icon k={asset.key} /></div>
                    <div className="text-sm font-sans font-semibold text-gray-900">{asset.name}</div>
                    <div className="text-xs text-gray-500 mt-0.5">{asset.desc}</div>
                  </button>
                );
              })}
            </div>

            <div className="mt-10 flex items-center justify-between">
              <GhostButton onClick={() => setStep(0)}>Back</GhostButton>
              <PrimaryButton onClick={() => setStep(2)} disabled={assets.size === 0}>
                Continue
              </PrimaryButton>
            </div>
          </div>
        )}

        {step === 2 && (
          <div>
            <h2 className="text-2xl font-sans font-bold text-gray-900 tracking-tight">What kind of investor are you?</h2>
            <p className="mt-2 text-sm text-gray-500">This sets your default portfolio constraints.</p>

            <div className="mt-6 grid grid-cols-3 gap-3">
              {RISK_OPTIONS.map((option) => {
                const selected = risk === option.key;
                return (
                  <button
                    key={option.key}
                    onClick={() => setRisk(option.key)}
                    className={`text-left p-4 rounded-xl border transition-all ${
                      selected ? "bg-gray-900 text-white border-gray-900" : "bg-white text-gray-900 border border-black/[0.12] hover:bg-black/[0.02]"
                    }`}
                  >
                    <div className="text-sm font-sans font-semibold">{option.name}</div>
                    <div className={`text-xs mt-1 ${selected ? "text-white/70" : "text-gray-500"}`}>{option.desc}</div>
                  </button>
                );
              })}
            </div>

            <p className="mt-5 text-xs font-mono text-gray-500">
              Default risk tolerance {riskProfile.risk_tolerance_default.toFixed(2)}. Crypto max {Math.round(riskProfile.constraints.crypto.max * 100)}%.
            </p>

            {error && <p className="mt-4 text-sm font-mono text-red-600">{error}</p>}

            <div className="mt-8 flex items-center justify-between">
              <GhostButton onClick={() => setStep(1)} disabled={submitting}>
                Back
              </GhostButton>
            </div>
            <button
              onClick={finish}
              disabled={submitting}
              className="mt-4 w-full py-3 bg-gray-900 text-white text-sm font-sans font-semibold rounded-lg hover:opacity-90 active:scale-[0.99] transition-all disabled:opacity-50"
            >
              {submitting ? "Creating Portfolio..." : "Start Investing"}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function UnderlineField({ label, value, onChange, small }) {
  return (
    <div>
      <label className="block text-[11px] font-sans font-semibold tracking-[0.14em] uppercase text-gray-400 mb-1">{label}</label>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className={`w-full bg-transparent border-0 border-b border-gray-200 focus:border-primary outline-none py-2 font-sans text-gray-900 transition-colors ${
          small ? "text-sm" : "text-lg"
        }`}
      />
    </div>
  );
}

function PrimaryButton({ children, ...rest }) {
  return (
    <button
      {...rest}
      className="px-5 py-2.5 bg-gray-900 text-white text-sm font-sans font-semibold rounded-lg hover:opacity-90 active:scale-[0.98] transition-all disabled:opacity-40 disabled:cursor-not-allowed"
    >
      {children}
    </button>
  );
}

function GhostButton({ children, ...rest }) {
  return (
    <button {...rest} className="px-4 py-2 text-sm font-sans font-medium text-gray-500 hover:text-gray-900 transition-colors disabled:opacity-50">
      {children}
    </button>
  );
}
