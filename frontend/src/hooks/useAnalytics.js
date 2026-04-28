import { useCallback, useEffect, useState } from 'react'

import { getAnalytics, getFactorExposure } from '../api/analytics'

export function useAnalytics(portfolioId) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const fetch = useCallback(async () => {
    if (!portfolioId) {
      setData(null)
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const [analytics, factors] = await Promise.all([
        getAnalytics(portfolioId),
        getFactorExposure(portfolioId),
      ])
      setData({ ...analytics, factor_exposure: factors })
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }, [portfolioId])

  useEffect(() => {
    fetch()
  }, [fetch])

  return { data, loading, error, refetch: fetch }
}
