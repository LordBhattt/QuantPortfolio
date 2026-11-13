import { useQuery } from '@tanstack/react-query'

import { getMonteCarlo, getRiskMetrics } from '../api/risk'

function getErrorMessage(error, fallback) {
  return error?.response?.data?.detail || error?.message || fallback
}

export function useRiskMetrics(portfolioId, enabled = true) {
  const query = useQuery({
    queryKey: ['risk-metrics', portfolioId],
    enabled: Boolean(portfolioId) && enabled,
    queryFn: () => getRiskMetrics(portfolioId),
    staleTime: 30_000,
    refetchInterval: 60_000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
  })

  return {
    data: query.data ?? null,
    loading: query.isLoading || query.isFetching,
    error: getErrorMessage(query.error, null),
    refetch: query.refetch,
  }
}

export function useMonteCarlo(portfolioId, nPaths = 1000, horizonDays = 252, enabled = true) {
  const query = useQuery({
    queryKey: ['monte-carlo', portfolioId, nPaths, horizonDays],
    enabled: Boolean(portfolioId) && enabled,
    queryFn: () => getMonteCarlo(portfolioId, { n_paths: nPaths, horizon_days: horizonDays }),
    staleTime: 5 * 60_000,
    refetchOnWindowFocus: false,
  })

  return {
    data: query.data ?? null,
    loading: query.isLoading || query.isFetching,
    error: getErrorMessage(query.error, null),
    refetch: query.refetch,
  }
}
