import client from './client'

export const getRiskMetrics = (portfolioId) =>
  client.get(`/api/v1/risk/${portfolioId}`).then((r) => r.data)

export const getMonteCarlo = (portfolioId, params = {}) =>
  client.get(`/api/v1/risk/${portfolioId}/monte-carlo`, { params }).then((r) => r.data)
