import client from './client'

export const getAnalytics = (portfolioId) =>
  client.get(`/api/v1/analytics/${portfolioId}`).then((r) => r.data)

export const getFactorExposure = (portfolioId) =>
  client.get(`/api/v1/analytics/${portfolioId}/factors`).then((r) => r.data)
