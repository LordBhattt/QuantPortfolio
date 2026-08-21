import client from './client'

export const getBacktest = (params = {}) =>
  client.get('/api/v1/backtest/', { params }).then((r) => r.data)
