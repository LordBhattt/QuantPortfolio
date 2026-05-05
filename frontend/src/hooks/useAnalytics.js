import { useQuery } from '@tanstack/react-query'

import { getAnalytics, getFactorExposure } from '../api/analytics'

function getErrorMessage(error, fallback) {
  return error?.response?.data?.detail || error?.message || fallback
}

export function useAnalytics(portfolioId) {
  const query = useQuery({
    queryKey: ['analytics', portfolioId],
    enabled: Boolean(portfolioId),
    queryFn: async () => {
      const [analytics, factors] = await Promise.all([
        getAnalytics(portfolioId),
        getFactorExposure(portfolioId),
      ])
      return { ...analytics, factor_exposure: factors }
    },
    staleTime: 60_000,
  })

  return {
    data: query.data ?? null,
    loading: query.isLoading || query.isFetching,
    error: getErrorMessage(query.error, null),
    refetch: query.refetch,
  }
}
