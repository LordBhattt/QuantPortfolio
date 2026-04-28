// Realistic mock data in INR.

export const mockHoldings = [
  { ticker: "RELIANCE.NS", name: "Reliance Industries", cls: "Stock", qty: 400, avg: 2840, current: 2940, pnl: 40000, pnlPct: 3.52, weight: 24.3 },
  { ticker: "BTC", name: "Bitcoin", cls: "Crypto", qty: 0.35, avg: 4800000, current: 5250000, pnl: 157500, pnlPct: 9.38, weight: 18.7 },
  { ticker: "AAPL", name: "Apple Inc.", cls: "Stock", qty: 60, avg: 14600, current: 15750, pnl: 69000, pnlPct: 7.88, weight: 14.2 },
  { ticker: "GLDBEES", name: "Gold ETF", cls: "Gold", qty: 250, avg: 5800, current: 6180, pnl: 95000, pnlPct: 6.55, weight: 12.8 },
  { ticker: "ETH", name: "Ethereum", cls: "Crypto", qty: 5, avg: 200000, current: 223000, pnl: 115000, pnlPct: 11.5, weight: 10.4 },
  { ticker: "NIFTYBEES", name: "Nifty 50 ETF", cls: "MF/ETF", qty: 400, avg: 235, current: 249, pnl: 5600, pnlPct: 5.95, weight: 8.6 },
  { ticker: "TCS.NS", name: "Tata Consultancy", cls: "Stock", qty: 120, avg: 3800, current: 3720, pnl: -9600, pnlPct: -2.11, weight: 6.7 },
  { ticker: "LIQUIDBEES", name: "Liquid Bond ETF", cls: "Bond", qty: 500, avg: 1000, current: 968, pnl: -16000, pnlPct: -3.19, weight: 4.3 },
];

// Portfolio value hovers around ₹1.2 Cr. 90 daily points.
export const mockPerformance = Array.from({ length: 90 }, (_, i) => {
  const base = 10500000;
  const drift = i * 22000;
  const noise = Math.sin(i / 6) * 180000 + Math.cos(i / 3) * 90000;
  const bench = Math.sin(i / 8) * 120000 + Math.cos(i / 4) * 60000;
  const d = new Date(2026, 0, i + 1);
  return {
    date: d.toISOString().slice(0, 10),
    portfolio: base + drift + noise,
    benchmark: base + drift * 0.7 + bench,
  };
});

export const mockSparkline = mockPerformance.slice(-30).map((p) => p.portfolio);

export const mockAllocation = [
  { name: "Stocks", key: "stocks", value: 45.2 },
  { name: "Crypto", key: "crypto", value: 29.1 },
  { name: "Gold", key: "gold", value: 12.8 },
  { name: "MF/ETF", key: "mf_etf", value: 8.6 },
  { name: "Bonds", key: "bonds", value: 4.3 },
];

export const mockFrontier = Array.from({ length: 40 }, (_, i) => {
  const risk = 0.05 + (i / 40) * 0.25;
  const ret = 0.04 + Math.sqrt(risk) * 0.55 - Math.random() * 0.01;
  return { risk, return: ret };
});

export const mockOptimalPoint = { risk: 0.142, return: 0.224 };

export const mockWeights = [
  { ticker: "RELIANCE.NS", current: 24.3, optimal: 18.5 },
  { ticker: "BTC", current: 18.7, optimal: 22.0 },
  { ticker: "AAPL", current: 14.2, optimal: 16.8 },
  { ticker: "GLDBEES", current: 12.8, optimal: 15.0 },
  { ticker: "ETH", current: 10.4, optimal: 8.2 },
  { ticker: "NIFTYBEES", current: 8.6, optimal: 10.0 },
  { ticker: "TCS.NS", current: 6.7, optimal: 5.5 },
  { ticker: "LIQUIDBEES", current: 4.3, optimal: 4.0 },
];

// Amounts in INR.
export const mockTrades = [
  { ticker: "RELIANCE.NS", cls: "Stock", action: "SELL", amount: -580000 },
  { ticker: "BTC", cls: "Crypto", action: "BUY", amount: 330000 },
  { ticker: "AAPL", cls: "Stock", action: "BUY", amount: 260000 },
  { ticker: "GLDBEES", cls: "Gold", action: "BUY", amount: 220000 },
  { ticker: "ETH", cls: "Crypto", action: "SELL", amount: -220000 },
  { ticker: "TCS.NS", cls: "Stock", action: "SELL", amount: -120000 },
];

export const mockMonteCarlo = (() => {
  const days = 252;
  const start = 12483200;
  const out = { p5: [], p25: [], p50: [], p75: [], p95: [] };
  for (let i = 0; i < days; i++) {
    const t = i / days;
    const mu = start * (1 + 0.22 * t);
    const sigma = start * 0.14 * Math.sqrt(t + 0.01);
    out.p5.push(mu - 1.96 * sigma);
    out.p25.push(mu - 0.67 * sigma);
    out.p50.push(mu);
    out.p75.push(mu + 0.67 * sigma);
    out.p95.push(mu + 1.96 * sigma);
  }
  return out;
})();

export const mockCorrTickers = ["RELIANCE", "AAPL", "BTC", "ETH", "GLD", "NIFTY", "BOND"];
export const mockCorrMatrix = (() => {
  const t = mockCorrTickers;
  const vals = [
    [1.0, 0.42, 0.18, 0.22, -0.05, 0.51, -0.28],
    [0.42, 1.0, 0.31, 0.34, -0.12, 0.78, -0.35],
    [0.18, 0.31, 1.0, 0.82, 0.08, 0.28, -0.18],
    [0.22, 0.34, 0.82, 1.0, 0.12, 0.32, -0.22],
    [-0.05, -0.12, 0.08, 0.12, 1.0, -0.08, 0.15],
    [0.51, 0.78, 0.28, 0.32, -0.08, 1.0, -0.38],
    [-0.28, -0.35, -0.18, -0.22, 0.15, -0.38, 1.0],
  ];
  const m = {};
  t.forEach((row, i) => {
    m[row] = {};
    t.forEach((col, j) => (m[row][col] = vals[i][j]));
  });
  return m;
})();

export const mockFactors = [
  { factor: "Mkt-RF", exposure: 0.82 },
  { factor: "SMB", exposure: 0.14 },
  { factor: "HML", exposure: -0.08 },
  { factor: "RMW", exposure: 0.21 },
  { factor: "CMA", exposure: -0.12 },
];

// Per-ticker 7d sparkline data, slightly randomized but deterministic-ish.
export const mockTickerSparks = Object.fromEntries(
  mockHoldings.map((h) => {
    const arr = Array.from({ length: 7 }, (_, i) => {
      const noise = Math.sin((h.ticker.charCodeAt(0) + i) / 2) * 0.02;
      return h.current * (1 + noise + (i - 3) * 0.004);
    });
    return [h.ticker, arr];
  }),
);

export const mockPortfolios = [
  { id: "demo-portfolio", name: "Core Portfolio" },
  { id: "retirement", name: "Retirement" },
  { id: "experimental", name: "Experimental" },
];

export const mockUser = {
  name: "Arjun Kumar",
  email: "arjun@quantportfolio.in",
  initials: "AK",
};
