import { useMemo, useState } from "react";
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid,
} from "recharts";

import FrontierScatter from "../components/charts/FrontierScatter";
import WeightsBar from "../components/charts/WeightsBar";
import ConstraintSliders from "../components/domain/ConstraintSliders";
import RebalanceTrades from "../components/domain/RebalanceTrades";
import UserViewsPanel from "../components/domain/UserViewsPanel";
import PageWrapper from "../components/layout/PageWrapper";
import Card from "../components/ui-qp/Card";
import Slider from "../components/ui-qp/Slider";
import Toggle from "../components/ui-qp/Toggle";
import { useOptimize } from "../hooks/useOptimize";
import { mapOptimizationResult } from "../lib/portfolioMappers";
import { usePortfolioStore } from "../store/portfolioStore";

export default function Optimize() {
  const portfolioId = usePortfolioStore((s) => s.portfolioId);
  const [riskTolerance, setRiskTolerance] = useState(0.5);
  const [constraints, setConstraints] = useState({
    stocks: { min: 10, max: 50 },
    crypto: { min: 0, max: 10 },
    gold: { min: 5, max: 20 },
    mf_etf: { min: 5, max: 30 },
    bonds: { min: 10, max: 40 },
  });
  const [userViews, setUserViews] = useState([]);
  const [useLstm, setUseLstm] = useState(true);
  const [useRegime, setUseRegime] = useState(true);

  const { run, result, loading, error } = useOptimize();
  const mappedResult = useMemo(() => mapOptimizationResult(result), [result]);

  const minSum = Object.values(constraints).reduce((acc, item) => acc + Number(item.min || 0), 0);
  const infeasible = minSum > 100;
  const canRun = Boolean(portfolioId) && !infeasible && !loading;

  return (
    <PageWrapper title="Optimize" subtitle="Black-Litterman plus Mean-Variance optimization">
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-4 mb-6">
        <div className="lg:col-span-2 animate-fadeUp opacity-0" style={{ animationDelay: "0ms" }}>
          <Card className="p-5">
            <div className="space-y-6">
              <div>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-[11px] font-sans font-medium tracking-[0.12em] uppercase text-muted-foreground">
                    Risk Tolerance
                  </span>
                  <span className="font-mono text-xs text-foreground">{riskTolerance.toFixed(2)}</span>
                </div>
                <Slider value={riskTolerance} onValueChange={setRiskTolerance} min={0} max={1} step={0.01} />
                <div className="flex justify-between mt-1.5">
                  <span className="text-[10px] font-mono text-muted-foreground">Min Variance</span>
                  <span className="text-[10px] font-mono text-muted-foreground">Max Return</span>
                </div>
              </div>

              <div className="h-px bg-black/[0.06]" />

              <div>
                <div className="flex items-center justify-between mb-4">
                  <span className="text-[11px] font-sans font-medium tracking-[0.12em] uppercase text-muted-foreground">
                    Asset Class Bounds
                  </span>
                  {infeasible && (
                    <span className="inline-flex items-center gap-1 font-mono text-[10px] uppercase tracking-wider px-2 py-0.5 bg-destructive/10 text-destructive rounded">
                      <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 8v5M12 16.5v.5"/></svg>
                      Infeasible
                    </span>
                  )}
                </div>
                <ConstraintSliders constraints={constraints} onChange={setConstraints} infeasible={infeasible} />
              </div>

              <div className="h-px bg-black/[0.06]" />

              <UserViewsPanel views={userViews} onChange={setUserViews} />

              <div className="h-px bg-black/[0.06]" />

              <div className="space-y-1">
                <Toggle checked={useLstm} onCheckedChange={setUseLstm} label="ML Forecast" hint="Use learned return priors" />
                <Toggle checked={useRegime} onCheckedChange={setUseRegime} label="Regime Scaling" hint="Adjust covariance by regime" />
              </div>

              {!portfolioId && <p className="text-sm font-mono text-amber-700">Create or select a portfolio before running optimization.</p>}
              {error && <p className="text-sm font-mono text-red-600">{error}</p>}

              <button
                onClick={() => run({ riskTolerance, constraints, userViews, useLstm, useRegime })}
                disabled={!canRun}
                className="w-full py-3 bg-foreground text-background text-sm font-sans font-semibold rounded-lg hover:opacity-90 active:scale-[0.98] transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {loading ? (
                  <span className="inline-flex items-center gap-2 font-mono text-xs tracking-wider">
                    <span className="w-3 h-3 border-2 border-background/40 border-t-background rounded-full animate-spin" />
                    OPTIMIZING...
                  </span>
                ) : (
                  "Run Optimization"
                )}
              </button>
            </div>
          </Card>
        </div>

        <div className="lg:col-span-3 animate-fadeUp opacity-0" style={{ animationDelay: "120ms" }}>
          <Card className="p-5 h-full">
            <div className="flex items-start justify-between mb-4">
              <div>
                <h2 className="text-sm font-semibold text-foreground">Efficient Frontier</h2>
                <p className="text-xs font-mono text-muted-foreground mt-0.5">Risk vs expected return</p>
              </div>
              {mappedResult.optimal && (
                <div className="text-right">
                  <div className="text-[10px] font-sans uppercase tracking-[0.12em] text-muted-foreground">Optimal</div>
                  <div className="font-mono text-xs text-foreground">
                    sigma {(mappedResult.optimal.risk * 100).toFixed(1)}% / mu {(mappedResult.optimal.return * 100).toFixed(1)}%
                  </div>
                </div>
              )}
            </div>
            <FrontierScatter data={mappedResult.frontier} optimal={mappedResult.optimal} />
            {!mappedResult.frontier.length && !loading && (
              <p className="text-center text-xs font-mono text-muted-foreground mt-4">
                Configure constraints and run optimization to see the frontier.
              </p>
            )}
          </Card>
        </div>
      </div>

      {result && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 animate-fadeUp opacity-0" style={{ animationDelay: "0ms" }}>
          <Card className="p-5">
            <h2 className="text-sm font-semibold text-foreground mb-4">Optimal Weights</h2>
            <WeightsBar data={mappedResult.weights} />
          </Card>
          <Card className="p-5">
            <h2 className="text-sm font-semibold text-foreground mb-4">Rebalancing Trades</h2>
            <RebalanceTrades trades={mappedResult.trades} />
          </Card>
        </div>
      )}

      {result?.diagnostics && (
        <DiagnosticsSection diagnostics={result.diagnostics} />
      )}
    </PageWrapper>
  );
}

function DiagnosticsSection({ diagnostics }) {
  const { per_asset, regime_probabilities, model_kind, ml_weight_used } = diagnostics;

  // Build grouped bar chart data
  const chartData = (per_asset || []).map((a) => ({
    ticker: a.ticker,
    Equilibrium: +(a.equilibrium_return_annual * 100).toFixed(1),
    Historical: +(a.historical_return_annual * 100).toFixed(1),
    ML: +(a.ml_return_annual * 100).toFixed(1),
    Momentum: +(a.momentum_return_annual * 100).toFixed(1),
    Blended: +(a.blended_return_annual * 100).toFixed(1),
  }));

  const modelBadge = {
    gbm: { label: "GBM model", color: "bg-indigo-100 text-indigo-700" },
    momentum: { label: "Momentum model", color: "bg-blue-100 text-blue-700" },
    lstm: { label: "LSTM model", color: "bg-purple-100 text-purple-700" },
    none: { label: "ML not used", color: "bg-gray-100 text-gray-500" },
  }[model_kind || "none"] || { label: "ML not used", color: "bg-gray-100 text-gray-500" };

  const { bull = 0.33, sideways = 0.34, bear = 0.33, current_regime = "sideways" } = regime_probabilities || {};

  return (
    <div className="mt-4 space-y-4">
      <Card className="p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-sm font-semibold text-foreground">Why This Allocation</h2>
          <span className={`text-xs px-2 py-0.5 rounded-full font-mono ${modelBadge.color}`}>
            Using: {modelBadge.label}
          </span>
        </div>

        {/* Regime probability bar */}
        <div className="mb-5">
          <p className="text-xs text-gray-500 mb-1">Market Regime Probabilities</p>
          <div className="flex h-5 rounded overflow-hidden text-xs font-mono">
            <div style={{ width: `${bull * 100}%` }} className="bg-emerald-400 flex items-center justify-center text-white">
              {bull > 0.1 ? `Bull ${(bull * 100).toFixed(0)}%` : ""}
            </div>
            <div style={{ width: `${sideways * 100}%` }} className="bg-amber-300 flex items-center justify-center text-gray-800">
              {sideways > 0.1 ? `Side ${(sideways * 100).toFixed(0)}%` : ""}
            </div>
            <div style={{ width: `${bear * 100}%` }} className="bg-red-400 flex items-center justify-center text-white">
              {bear > 0.1 ? `Bear ${(bear * 100).toFixed(0)}%` : ""}
            </div>
          </div>
          <p className="text-xs text-gray-400 mt-1">Current regime: <span className="font-mono font-semibold capitalize">{current_regime}</span></p>
        </div>

        {/* Return component bar chart */}
        {chartData.length > 0 && (
          <div>
            <p className="text-xs text-gray-500 mb-2">Expected Return Components (annual %)</p>
            <ResponsiveContainer width="100%" height={Math.max(220, chartData.length * 50)}>
              <BarChart data={chartData} margin={{ top: 4, right: 16, left: 8, bottom: 4 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
                <XAxis dataKey="ticker" tick={{ fontSize: 10 }} />
                <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => `${v}%`} />
                <Tooltip formatter={(v) => [`${v}%`]} />
                <Legend />
                <Bar dataKey="Equilibrium" fill="#6366f1" radius={[2, 2, 0, 0]} />
                <Bar dataKey="Historical" fill="#10b981" radius={[2, 2, 0, 0]} />
                <Bar dataKey="ML" fill="#f59e0b" radius={[2, 2, 0, 0]} />
                <Bar dataKey="Momentum" fill="#8b5cf6" radius={[2, 2, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </Card>
    </div>
  );
}
