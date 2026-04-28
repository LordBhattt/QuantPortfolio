import { useCallback, useEffect, useState } from 'react'

import { getCurrentUser } from '../api/auth'
import { usePortfolioStore } from '../store/portfolioStore'

export function useCurrentUser() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const token = usePortfolioStore((s) => s.token)

  const fetch = useCallback(async () => {
    if (!token) {
      setData(null)
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      setData(await getCurrentUser())
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }, [token])

  useEffect(() => {
    fetch()
  }, [fetch])

  return { data, loading, error, refetch: fetch }
}
