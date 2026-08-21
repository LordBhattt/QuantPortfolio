import { useQuery } from '@tanstack/react-query'

import { getBacktest } from '../api/backtest'

function getErrorMessage(error, fallback) {
  return error?.response?.data?.detail || error?.message || fallback
}

export function useBacktest({ lookbackDays = 504, transactionCostBps = 10, baseline = 'equal_weight' } = {}) {
  const query = useQuery({
    queryKey: ['backtest', lookbackDays, transactionCostBps, baseline],
    queryFn: () => getBacktest({ lookback_days: lookbackDays, transaction_cost_bps: transactionCostBps, baseline }),
    staleTime: 5 * 60_000,
    retry: false,
  })

  return {
    data: query.data ?? null,
    loading: query.isLoading || query.isFetching,
    error: getErrorMessage(query.error, null),
    refetch: query.refetch,
  }
}
