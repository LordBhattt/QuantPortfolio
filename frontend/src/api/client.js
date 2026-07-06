import axios from 'axios'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL || '/',
  withCredentials: true,
})

export function getApiErrorMessage(error, fallback = 'Request failed') {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) return detail.map((item) => item.msg || item.message || String(item)).join(', ')
  if (error?.code === 'ERR_NETWORK') return 'Backend API is not reachable. Start the FastAPI server on port 8000.'
  return error?.message || fallback
}

function isAuthFormRequest(config) {
  const url = config?.url || ''
  return url.includes('/api/v1/auth/token') || url.includes('/api/v1/auth/register')
}

// Handle expired sessions globally, while letting auth forms show their own errors.
client.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401 && !isAuthFormRequest(err.config) && window.location.pathname !== '/login') {
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default client
