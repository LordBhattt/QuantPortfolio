import { useQuery } from '@tanstack/react-query'

import { getAnalytics } from '../api/analytics'

function getErrorMessage(error, fallback) {
  return error?.response?.data?.detail || error?.message || fallback
}

export function useAnalytics(portfolioId, enabled = true) {
  const query = useQuery({
    queryKey: ['analytics', portfolioId],
    enabled: Boolean(portfolioId) && enabled,
    queryFn: () => getAnalytics(portfolioId),
    staleTime: 30_000,
    refetchInterval: 30_000,
    refetchIntervalInBackground: false,
    refetchOnWindowFocus: true,
  })

  return {
    data: query.data ?? null,
    loading: query.isLoading,
    refreshing: query.isFetching && !query.isLoading,
    error: getErrorMessage(query.error, null),
    refetch: query.refetch,
  }
}
