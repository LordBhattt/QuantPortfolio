import client from './client'

export const searchAssets = (q, assetClass) =>
  client.get('/api/v1/assets/', { params: { q, class: assetClass } }).then((r) => r.data)
