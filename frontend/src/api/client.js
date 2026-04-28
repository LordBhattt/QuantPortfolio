import axios from 'axios'

const client = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  withCredentials: false,
})

// Attach JWT on every request
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('qp_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Handle 401 globally — clear token and redirect to login
client.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('qp_token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default client
