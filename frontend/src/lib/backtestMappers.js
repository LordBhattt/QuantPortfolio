/** Backtest data mappers - reshape API response for charts and tables. */

const INR = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 0 });
const PCT = (v) => `${(v * 100).toFixed(1)}%`;
const SIGNED_PCT = (v) => `${v >= 0 ? "+" : ""}${(v * 100).toFixed(1)}%`;

export function formatINRNum(v) {
  return INR.format(v);
}

export function formatBacktestMetrics(strategies) {
  if (!strategies) return [];
  return strategies.map((s) => ({
    ...s,
    final_value_fmt: formatINRNum(s.final_value),
    total_profit_fmt: `${s.total_profit_inr >= 0 ? "+" : ""}${formatINRNum(Math.abs(s.total_profit_inr))}`,
    cagr_fmt: SIGNED_PCT(s.cagr),
    vol_fmt: PCT(s.volatility),
    sharpe_fmt: s.sharpe.toFixed(2),
    sortino_fmt: s.sortino.toFixed(2),
    drawdown_fmt: PCT(Math.abs(s.max_drawdown)),
    calmar_fmt: s.calmar.toFixed(2),
    turnover_fmt: PCT(s.avg_turnover),
  }));
}

export function bestPerColumn(rows) {
  if (!rows || rows.length === 0) return {};
  const best = {};
  const higherBetter = ["final_value", "total_profit_inr", "cagr", "sharpe", "sortino", "calmar"];
  const lowerBetter = ["volatility", "max_drawdown", "avg_turnover"];
  for (const col of higherBetter) {
    const vals = rows.map((r) => r[col]).filter((v) => v != null && isFinite(v));
    if (vals.length) best[col] = Math.max(...vals);
  }
  for (const col of lowerBetter) {
    const vals = rows.map((r) => r[col]).filter((v) => v != null && isFinite(v));
    if (vals.length) best[col] = Math.min(...vals);
  }
  return best;
}
