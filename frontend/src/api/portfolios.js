import client from './client'

export const getPortfolios = () =>
  client.get('/api/v1/portfolios/').then((r) => r.data)

export const createPortfolio = (payload) =>
  client.post('/api/v1/portfolios/', payload).then((r) => r.data)

export const getPortfolio = (id) =>
  client.get(`/api/v1/portfolios/${id}`).then((r) => r.data)

export const updatePortfolio = (id, payload) =>
  client.patch(`/api/v1/portfolios/${id}`, payload).then((r) => r.data)

export const deletePortfolio = (id) =>
  client.delete(`/api/v1/portfolios/${id}`)

export const getHoldings = (portfolioId) =>
  client.get(`/api/v1/portfolios/${portfolioId}/holdings`).then((r) => r.data)

export const addHolding = (portfolioId, payload) =>
  client.post(`/api/v1/portfolios/${portfolioId}/holdings`, payload).then((r) => r.data)

export const deleteHolding = (portfolioId, holdingId) =>
  client.delete(`/api/v1/portfolios/${portfolioId}/holdings/${holdingId}`)
