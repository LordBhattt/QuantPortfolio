import { useQuery } from '@tanstack/react-query'

import { getCurrentUser } from '../api/auth'
import { getApiErrorMessage } from '../api/client'

function getErrorMessage(error, fallback) {
  return getApiErrorMessage(error, fallback)
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
    loading: query.isLoading,
    error: getErrorMessage(query.error, null),
    refetch: query.refetch,
  }
}
