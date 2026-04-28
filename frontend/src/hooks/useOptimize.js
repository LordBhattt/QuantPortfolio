import { useState } from "react";

import { runOptimization } from "../api/optimization";
import { usePortfolioStore } from "../store/portfolioStore";

export function useOptimize() {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const portfolioId = usePortfolioStore((s) => s.portfolioId);
  const setRegime = usePortfolioStore((s) => s.setRegime);

  const run = async ({ riskTolerance, constraints, userViews, useLstm, useRegime }) => {
    if (!portfolioId) {
      setError("Create or select a portfolio before running optimization.");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const mappedConstraints = constraints
        ? Object.fromEntries(
            Object.entries(constraints).map(([key, value]) => [
              key,
              {
                min: Number(value.min) / 100,
                max: Number(value.max) / 100,
              },
            ]),
          )
        : null;

      const payload = {
        portfolio_id: portfolioId,
        risk_tolerance: riskTolerance,
        constraints: mappedConstraints,
        user_views: userViews.map((view) => ({
          ticker: view.ticker,
          expected_return: view.expected,
          confidence: view.confidence,
        })),
        use_lstm_forecasts: useLstm,
        use_regime_scaling: useRegime,
      };

      const data = await runOptimization(payload);
      setResult(data);
      setRegime(data.regime);
    } catch (err) {
      setError(err.response?.data?.detail || "Optimization failed");
    } finally {
      setLoading(false);
    }
  };

  return { run, result, loading, error };
}
