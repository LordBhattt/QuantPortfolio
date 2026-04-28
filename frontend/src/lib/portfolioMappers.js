const ASSET_CLASS_LABELS = {
  stock: "Stock",
  stocks: "Stock",
  crypto: "Crypto",
  gold: "Gold",
  mf_etf: "MF/ETF",
  bond: "Bond",
  bonds: "Bond",
};

export function toAssetClassLabel(value) {
  if (!value) return "Asset";
  return ASSET_CLASS_LABELS[value] || value;
}

export function mapAllocationData(assetClassAllocation = {}) {
  return Object.entries(assetClassAllocation)
    .map(([key, value]) => ({
      key,
      name: toAssetClassLabel(key),
      value: Number(value || 0) * 100,
    }))
    .sort((left, right) => right.value - left.value);
}

export function mapFactorExposure(factorExposure) {
  if (!factorExposure) return [];
  return [
    { factor: "Mkt-RF", exposure: factorExposure.beta_market ?? 0 },
    { factor: "SMB", exposure: factorExposure.beta_smb ?? 0 },
    { factor: "HML", exposure: factorExposure.beta_hml ?? 0 },
    { factor: "RMW", exposure: factorExposure.beta_rmw ?? 0 },
    { factor: "CMA", exposure: factorExposure.beta_cma ?? 0 },
  ];
}

export function mergeHoldingsWithAnalytics(holdings = [], analytics = null) {
  const breakdown = analytics?.holdings_breakdown || [];
  const breakdownMap = new Map(breakdown.map((item) => [item.ticker, item]));
  const sourceRows = holdings.length
    ? holdings
    : breakdown.map((item) => ({
        id: item.ticker,
        ticker: item.ticker,
        quantity: item.quantity || 0,
        avg_buy_price: item.avg_buy_price_inr || 0,
        buy_currency: "INR",
      }));

  return sourceRows
    .map((holding) => {
      const details = breakdownMap.get(holding.ticker) || {};
      const quantity = Number(details.quantity ?? holding.quantity ?? 0);
      const avg = Number(details.avg_buy_price_inr ?? holding.avg_buy_price ?? 0);
      const current = Number(details.current_price_inr ?? avg);
      const spark = details.sparkline_inr?.length
        ? details.sparkline_inr
        : Array.from({ length: 7 }, () => current);

      return {
        id: holding.id || holding.ticker,
        ticker: holding.ticker,
        name: details.name || holding.ticker,
        cls: toAssetClassLabel(details.asset_class),
        qty: quantity,
        avg,
        current,
        pnl: Number(details.pnl_inr ?? 0),
        pnlPct: Number(details.pnl_pct ?? 0) * 100,
        weight: Number(details.weight ?? 0) * 100,
        spark,
      };
    })
    .sort((left, right) => right.weight - left.weight);
}

export function mapOptimizationResult(result) {
  if (!result) {
    return {
      frontier: [],
      optimal: null,
      weights: [],
      trades: [],
    };
  }

  const usdInrRate = Number(result.usd_inr_rate || 83.5);
  const totalCurrent = result.optimal_weights.reduce((sum, item) => sum + Number(item.current_value_usd || 0), 0);

  return {
    frontier: result.efficient_frontier.map((point) => ({
      risk: point.volatility,
      return: point.expected_return,
      sharpe: point.sharpe,
    })),
    optimal: {
      risk: result.portfolio_volatility,
      return: result.portfolio_return,
    },
    weights: result.optimal_weights.map((item) => ({
      ticker: item.ticker,
      current: totalCurrent > 0 ? (Number(item.current_value_usd || 0) / totalCurrent) * 100 : 0,
      optimal: Number(item.weight || 0) * 100,
    })),
    trades: result.rebalance_trades.map((item) => ({
      ticker: item.ticker,
      cls: toAssetClassLabel(item.asset_class),
      action: Number(item.trade_delta_usd || 0) >= 0 ? "BUY" : "SELL",
      amount: Number(item.trade_delta_usd || 0) * usdInrRate,
    })),
  };
}
