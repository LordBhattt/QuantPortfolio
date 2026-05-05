import client from './client'

export const getAlerts = () => client.get('/api/v1/alerts/').then((response) => response.data)

export const markAlertRead = (alertId) => client.patch(`/api/v1/alerts/${alertId}/read`)

export const markAllAlertsRead = () => client.patch('/api/v1/alerts/read-all')