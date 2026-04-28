import client from './client'

export const runOptimization = (payload) =>
  client.post('/api/v1/optimize/', payload).then((r) => r.data)
