import { useCallback, useEffect, useState } from 'react'

import { getHoldings, getPortfolio, getPortfolios } from '../api/portfolios'
import { usePortfolioStore } from '../store/portfolioStore'

export function usePortfolios() {
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const portfolioId = usePortfolioStore((s) => s.portfolioId)
  const setPortfolio = usePortfolioStore((s) => s.setPortfolio)

  const fetch = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const portfolios = await getPortfolios()
      setData(portfolios)
      if (portfolios.length > 0) {
        const selected = portfolios.find((portfolio) => portfolio.id === portfolioId)
        const fallback = selected || portfolios[0]
        setPortfolio(fallback.id, fallback.name)
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message)
    } finally {
      setLoading(false)
    }
  }, [portfolioId, setPortfolio])

  useEffect(() => {
    fetch()
  }, [fetch])

  return { data, loading, error, refetch: fetch }
}

export function usePortfolio(portfolioId) {
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
      setData(await getPortfolio(portfolioId))
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

export function useHoldings(portfolioId) {
  const [data, setData] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const fetch = useCallback(async () => {
    if (!portfolioId) {
      setData([])
      setLoading(false)
      return
    }
    setLoading(true)
    setError(null)
    try {
      const holdings = await getHoldings(portfolioId)
      setData(holdings)
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
