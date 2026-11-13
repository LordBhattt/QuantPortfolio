import { useState } from "react";
import {
  LineChart, Line, AreaChart, Area, BarChart, Bar,
  XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid,
} from "recharts";

import PageWrapper from "../components/layout/PageWrapper";
import Card from "../components/ui-qp/Card";
import { runBacktest } from "../api/backtest";
import { usePortfolioStore } from "../store/portfolioStore";
import { formatBacktestMetrics, bestPerColumn } from "../lib/backtestMappers";

const COLORS = ["#6366f1", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#06b6d4"];

const STRATEGY_COLORS = {
  "Optimized": "#6366f1",
  "QP Smart": "#0f766e",
  "Equal Weight": "#10b981",
  "Buy and Hold": "#f59e0b",
  "Min Variance": "#8b5cf6",
  "SPY": "#94a3b8",
  "NIFTY": "#64748b",
};

const fmtDate = (d) => {
  if (!d) return "";
  return String(d).slice(0, 7); // YYYY-MM
};

const fmtINR = (v) =>
  new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 }).format(v);

const fmtPct = (v) => `${(v * 100).toFixed(1)}%`;
const fmtSigned = (v) => `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%`;
const fmtNum = (v) => (v == null ? "-" : Number(v).toFixed(2));

function Toggle({ label, checked, onChange }) {
  return (
    <label className="flex items-center gap-2 cursor-pointer select-none">
      <div
        onClick={() => onChange(!checked)}
        className={`w-10 h-5 rounded-full transition-colors ${checked ? "bg-indigo-500" : "bg-gray-200"} relative`}
      >
        <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform ${checked ? "translate-x-5" : "translate-x-0.5"}`} />
      </div>
      <span className="text-sm text-gray-700">{label}</span>
    </label>
  );
}

function MetricsTable({ strategies }) {
  const rows = formatBacktestMetrics(strategies);
  const best = bestPerColumn(strategies);

  const cols = [
    { key: "final_value", label: "Final Value", fmt: (r) => fmtINR(r.final_value), better: "max" },
    { key: "total_profit_inr", label: "Total Profit", fmt: (r) => `${r.total_profit_inr >= 0 ? "+" : ""}${fmtINR(Math.abs(r.total_profit_inr))}`, better: "max" },
    { key: "cagr", label: "CAGR", fmt: (r) => fmtSigned(r.cagr), better: "max" },
    { key: "volatility", label: "Vol", fmt: (r) => fmtPct(r.volatility), better: "min" },
    { key: "sharpe", label: "Sharpe", fmt: (r) => fmtNum(r.sharpe), better: "max" },
    { key: "sortino", label: "Sortino", fmt: (r) => fmtNum(r.sortino), better: "max" },
    { key: "max_drawdown", label: "Max DD", fmt: (r) => fmtPct(Math.abs(r.max_drawdown)), better: "min" },
    { key: "calmar", label: "Calmar", fmt: (r) => fmtNum(r.calmar), better: "max" },
    { key: "avg_turnover", label: "Turnover", fmt: (r) => fmtPct(r.avg_turnover), better: "min" },
  ];

  const isBest = (row, col) => {
    const v = row[col.key];
    if (v == null || !isFinite(v)) return false;
    const b = best[col.key];
    return b != null && Math.abs(v - b) < 1e-9;
  };

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-gray-100">
            <th className="text-left py-2 pr-4 font-medium text-gray-500">Strategy</th>
            {cols.map((c) => (
              <th key={c.key} className="text-right py-2 px-2 font-medium text-gray-500 whitespace-nowrap">{c.label}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {strategies.map((row, i) => (
            <tr key={row.name} className={i % 2 === 0 ? "bg-white" : "bg-gray-50"}>
              <td className="py-2 pr-4 font-mono text-xs font-semibold" style={{ color: STRATEGY_COLORS[row.name] || "#374151" }}>
                {row.name}
              </td>
              {cols.map((col) => (
                <td
                  key={col.key}
                  className={`py-2 px-2 text-right font-mono text-xs whitespace-nowrap ${isBest(row, col) ? "text-emerald-700 font-bold bg-emerald-50 rounded" : "text-gray-700"}`}
                >
                  {col.fmt(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function EquityCurve({ equityCurves }) {
  const names = Object.keys(equityCurves || {});
  if (!names.length) return null;

  // Merge all strategy curves into one array by date
  const dateMap = {};
  for (const name of names) {
    for (const pt of equityCurves[name] || []) {
      if (!dateMap[pt.date]) dateMap[pt.date] = { date: pt.date };
      dateMap[pt.date][name] = pt.value;
    }
  }
  const data = Object.values(dateMap).sort((a, b) => a.date.localeCompare(b.date));
  const sampled = data.filter((_, i) => i % 5 === 0 || i === data.length - 1);

  return (
    <ResponsiveContainer width="100%" height={320}>
      <LineChart data={sampled} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
        <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={fmtDate} />
        <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => `${(v / 1000).toFixed(0)}k`} />
        <Tooltip formatter={(v, name) => [fmtINR(v), name]} labelFormatter={(l) => `Date: ${l}`} />
        <Legend />
        {names.map((name, i) => (
          <Line
            key={name}
            type="monotone"
            dataKey={name}
            stroke={STRATEGY_COLORS[name] || COLORS[i % COLORS.length]}
            dot={false}
            strokeWidth={name === "Optimized" ? 2.5 : 1.5}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

function DrawdownChart({ drawdownCurves }) {
  const names = Object.keys(drawdownCurves || {});
  if (!names.length) return null;

  const dateMap = {};
  for (const name of names) {
    for (const pt of drawdownCurves[name] || []) {
      if (!dateMap[pt.date]) dateMap[pt.date] = { date: pt.date };
      dateMap[pt.date][name] = pt.drawdown * 100;
    }
  }
  const data = Object.values(dateMap).sort((a, b) => a.date.localeCompare(b.date));
  const sampled = data.filter((_, i) => i % 5 === 0 || i === data.length - 1);

  return (
    <ResponsiveContainer width="100%" height={200}>
      <AreaChart data={sampled} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
        <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={fmtDate} />
        <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => `${v.toFixed(0)}%`} />
        <Tooltip formatter={(v, name) => [`${v.toFixed(1)}%`, name]} />
        <Legend />
        {names.slice(0, 4).map((name, i) => (
          <Area
            key={name}
            type="monotone"
            dataKey={name}
            stroke={STRATEGY_COLORS[name] || COLORS[i % COLORS.length]}
            fill={STRATEGY_COLORS[name] || COLORS[i % COLORS.length]}
            fillOpacity={0.15}
            dot={false}
            strokeWidth={1.5}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  );
}

function WeightsChart({ weightsHistory }) {
  if (!weightsHistory || weightsHistory.length === 0) return null;
  const tickers = Object.keys(weightsHistory[0] || {}).filter((k) => k !== "date");
  const sampled = weightsHistory.filter((_, i) => i % 3 === 0 || i === weightsHistory.length - 1);

  return (
    <ResponsiveContainer width="100%" height={260}>
      <AreaChart data={sampled} margin={{ top: 8, right: 16, left: 8, bottom: 8 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
        <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={fmtDate} />
        <YAxis tick={{ fontSize: 10 }} tickFormatter={(v) => `${(v * 100).toFixed(0)}%`} domain={[0, 1]} />
        <Tooltip formatter={(v, name) => [`${(v * 100).toFixed(1)}%`, name]} />
        <Legend />
        {tickers.map((t, i) => (
          <Area
            key={t}
            type="monotone"
            dataKey={t}
            stackId="1"
            stroke={COLORS[i % COLORS.length]}
            fill={COLORS[i % COLORS.length]}
            fillOpacity={0.75}
            dot={false}
            strokeWidth={0}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  );
}

export default function Backtest() {
  const portfolioId = usePortfolioStore((s) => s.portfolioId);
  const [params, setParams] = useState({
    lookback_years: 3,
    rebalance: "monthly",
    risk_tolerance: 0.5,
    cost_bps: 10,
    use_ml: false,
    use_regime: true,
  });
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const handleRun = async () => {
    if (!portfolioId) return;
    setLoading(true);
    setError(null);
    try {
      const data = await runBacktest({ portfolio_id: portfolioId, ...params });
      setResult(data);
    } catch (e) {
      setError(e?.response?.data?.detail || e.message || "Backtest failed");
    } finally {
      setLoading(false);
    }
  };

  const headlineIsPositive =
    result && result.headline && !result.headline.includes("-INR");

  return (
    <PageWrapper title="Backtest Lab" subtitle="Walk-forward portfolio simulation - no lookahead">
      {/* Controls */}
      <Card className="p-5 mb-6">
        <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 items-end">
          <div>
            <label className="block text-xs text-gray-500 mb-1">Lookback</label>
            <select
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              value={params.lookback_years}
              onChange={(e) => setParams((p) => ({ ...p, lookback_years: Number(e.target.value) }))}
            >
              {[1, 2, 3, 4, 5].map((y) => <option key={y} value={y}>{y}Y</option>)}
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Rebalance</label>
            <select
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              value={params.rebalance}
              onChange={(e) => setParams((p) => ({ ...p, rebalance: e.target.value }))}
            >
              <option value="weekly">Weekly</option>
              <option value="monthly">Monthly</option>
              <option value="quarterly">Quarterly</option>
            </select>
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Risk Tolerance: {params.risk_tolerance.toFixed(1)}</label>
            <input
              type="range" min={0} max={1} step={0.1}
              value={params.risk_tolerance}
              onChange={(e) => setParams((p) => ({ ...p, risk_tolerance: Number(e.target.value) }))}
              className="w-full accent-indigo-500"
            />
          </div>
          <div>
            <label className="block text-xs text-gray-500 mb-1">Cost (bps)</label>
            <input
              type="number" min={0} max={50}
              className="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm font-mono"
              value={params.cost_bps}
              onChange={(e) => setParams((p) => ({ ...p, cost_bps: Number(e.target.value) }))}
            />
          </div>
          <div className="flex flex-col gap-2">
            <Toggle label="ML Forecast" checked={params.use_ml} onChange={(v) => setParams((p) => ({ ...p, use_ml: v }))} />
            <Toggle label="Regime" checked={params.use_regime} onChange={(v) => setParams((p) => ({ ...p, use_regime: v }))} />
          </div>
          <button
            onClick={handleRun}
            disabled={loading || !portfolioId}
            className="h-10 px-5 rounded-lg bg-indigo-600 text-white text-sm font-semibold hover:bg-indigo-700 disabled:opacity-50 flex items-center justify-center gap-2"
          >
            {loading ? (
              <><span className="animate-spin inline-block w-4 h-4 border-2 border-white border-t-transparent rounded-full" /> Running...</>
            ) : "Run Backtest"}
          </button>
        </div>
      </Card>

      {error && (
        <Card className="p-4 mb-6 border border-red-200 bg-red-50">
          <p className="text-sm font-mono text-red-700">{error}</p>
        </Card>
      )}

      {result && (
        <>
          {/* Headline */}
          <Card className={`p-5 mb-6 border ${headlineIsPositive ? "border-emerald-200 bg-emerald-50" : "border-red-200 bg-red-50"}`}>
            <p className={`text-lg font-bold ${headlineIsPositive ? "text-emerald-800" : "text-red-800"}`}>
              {result.headline}
            </p>
            <p className="text-xs text-gray-500 mt-1">
              {params.lookback_years}Y walk-forward | {params.rebalance} rebalance | cost {params.cost_bps}bps | starting INR 1,00,000
            </p>
            {result.selected_settings?.config && (
              <p className="text-xs text-gray-600 mt-2">
                QP Smart settings: {result.selected_settings.config} (selected through {result.selected_settings.train_end})
              </p>
            )}
          </Card>

          {/* Metrics table */}
          <Card className="p-5 mb-6">
            <h3 className="text-sm font-semibold text-gray-600 mb-4">Strategy Comparison</h3>
            <MetricsTable strategies={result.strategies} />
          </Card>

          {/* Equity curve */}
          <Card className="p-5 mb-6">
            <h3 className="text-sm font-semibold text-gray-600 mb-4">Equity Curves (INR)</h3>
            <EquityCurve equityCurves={result.equity_curves} />
          </Card>

          {/* Drawdown */}
          <Card className="p-5 mb-6">
            <h3 className="text-sm font-semibold text-gray-600 mb-4">Drawdown (Underwater)</h3>
            <DrawdownChart drawdownCurves={result.drawdown_curves} />
          </Card>

          {/* Weights history */}
          {result.weights_history && result.weights_history.length > 0 && (
            <Card className="p-5 mb-6">
              <h3 className="text-sm font-semibold text-gray-600 mb-4">QP Smart - Weights Over Time</h3>
              <WeightsChart weightsHistory={result.weights_history} />
            </Card>
          )}
        </>
      )}

      {!result && !loading && (
        <Card className="p-10 text-center">
          <p className="text-gray-400 text-sm">Configure parameters above and click Run Backtest to see results.</p>
          <p className="text-gray-300 text-xs mt-2">Walk-forward with no lookahead - each rebalance only uses data available at that date.</p>
        </Card>
      )}
    </PageWrapper>
  );
}
