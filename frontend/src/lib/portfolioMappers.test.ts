import { describe, expect, it } from "vitest";

import {
  mapAllocationData,
  mapOptimizationResult,
  mergeHoldingsWithAnalytics,
  toAssetClassLabel,
} from "./portfolioMappers";

describe("portfolioMappers", () => {
  it("maps allocation data in descending order", () => {
    const result = mapAllocationData({ crypto: 0.2, stock: 0.5, bonds: 0.3 });

    expect(result.map((entry) => entry.key)).toEqual(["stock", "bonds", "crypto"]);
    expect(result[0]).toMatchObject({ name: "Stock", value: 50 });
  });

  it("merges holdings with analytics breakdown", () => {
    const result = mergeHoldingsWithAnalytics([], {
      holdings_breakdown: [
        {
          ticker: "BTC",
          name: "Bitcoin",
          asset_class: "crypto",
          quantity: 2,
          avg_buy_price_inr: 100,
          current_price_inr: 150,
          pnl_inr: 100,
          pnl_pct: 0.25,
          weight: 0.4,
          sparkline_inr: [1, 2, 3],
        },
      ],
    });

    expect(result).toHaveLength(1);
    expect(result[0]).toMatchObject({
      ticker: "BTC",
      name: "Bitcoin",
      cls: "Crypto",
      qty: 2,
      avg: 100,
      current: 150,
      pnl: 100,
      pnlPct: 25,
      weight: 40,
      spark: [1, 2, 3],
    });
  });

  it("maps optimization results to chart-friendly data", () => {
    const result = mapOptimizationResult({
      usd_inr_rate: 83.5,
      portfolio_return: 0.12,
      portfolio_volatility: 0.08,
      efficient_frontier: [{ expected_return: 0.1, volatility: 0.07, sharpe: 1.2 }],
      optimal_weights: [
        {
          ticker: "BTC",
          current_value_usd: 100,
          weight: 0.6,
          asset_class: "crypto",
        },
        {
          ticker: "AAPL",
          current_value_usd: 200,
          weight: 0.4,
          asset_class: "stock",
        },
      ],
      rebalance_trades: [
        { ticker: "BTC", asset_class: "crypto", trade_delta_usd: 5 },
        { ticker: "AAPL", asset_class: "stock", trade_delta_usd: -10 },
      ],
    });

    expect(result.frontier).toEqual([{ risk: 0.07, return: 0.1, sharpe: 1.2 }]);
    expect(result.optimal).toEqual({ risk: 0.08, return: 0.12 });
    expect(result.weights).toEqual([
      { ticker: "BTC", current: 33.33333333333333, optimal: 60 },
      { ticker: "AAPL", current: 66.66666666666666, optimal: 40 },
    ]);
    expect(result.trades).toEqual([
      { ticker: "BTC", cls: "Crypto", action: "BUY", amount: 417.5 },
      { ticker: "AAPL", cls: "Stock", action: "SELL", amount: -835 },
    ]);
  });

  it("returns a fallback label for unknown classes", () => {
    expect(toAssetClassLabel("commodities")).toBe("commodities");
  });
});