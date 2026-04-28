import client from './client'

export async function register({ email, password, full_name }) {
  const { data } = await client.post('/api/v1/auth/register', {
    email,
    password,
    full_name,
  })
  return data
}

export async function login({ email, password }) {
  const params = new URLSearchParams()
  params.append('username', email)
  params.append('password', password)
  const { data } = await client.post('/api/v1/auth/token', params, {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
  })
  return data
}

export async function getCurrentUser() {
  const { data } = await client.get('/api/v1/auth/me')
  return data
}
