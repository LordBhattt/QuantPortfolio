import { useQuery } from '@tanstack/react-query'

import { getCurrentUser } from '../api/auth'

function getErrorMessage(error, fallback) {
  return error?.response?.data?.detail || error?.message || fallback
}

export function useCurrentUser() {
  const query = useQuery({
    queryKey: ['current-user'],
    queryFn: getCurrentUser,
    retry: false,
    staleTime: 60_000,
  })

  return {
    data: query.data ?? null,
    loading: query.isLoading || query.isFetching,
    error: getErrorMessage(query.error, null),
    refetch: query.refetch,
  }
}
