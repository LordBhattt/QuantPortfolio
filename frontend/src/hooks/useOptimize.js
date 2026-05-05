import { useMutation } from "@tanstack/react-query";

import { runOptimization } from "../api/optimization";
import { usePortfolioStore } from "../store/portfolioStore";

function getErrorMessage(error, fallback) {
  return error?.response?.data?.detail || error?.message || fallback;
}

export function useOptimize() {
  const portfolioId = usePortfolioStore((s) => s.portfolioId);
  const setRegime = usePortfolioStore((s) => s.setRegime);

  const mutation = useMutation({
    mutationFn: async ({ riskTolerance, constraints, userViews, useLstm, useRegime }) => {
      if (!portfolioId) {
        throw new Error("Create or select a portfolio before running optimization.");
      }

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

      return runOptimization(payload);
    },
    onSuccess: (data) => {
      setRegime(data.regime);
    },
  });

  const run = (payload) => mutation.mutate(payload);

  return {
    run,
    result: mutation.data ?? null,
    loading: mutation.isPending,
    error: getErrorMessage(mutation.error, null),
  };
}
