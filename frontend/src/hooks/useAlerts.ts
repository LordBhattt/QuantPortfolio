import { useQuery } from '@tanstack/react-query'

import { getAlerts } from '../api/alerts'

export function useAlerts() {
  const query = useQuery({
    queryKey: ['alerts'],
    queryFn: getAlerts,
    refetchInterval: 60_000,
    staleTime: 30_000,
    retry: false,
  })

  return {
    data: query.data ?? [],
    loading: query.isLoading || query.isFetching,
    refetch: query.refetch,
  }
}