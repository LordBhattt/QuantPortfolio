import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { login } from '../api/auth'
import { usePortfolioStore } from '../store/portfolioStore'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const setToken = usePortfolioStore((s) => s.setToken)
  const navigate = useNavigate()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const { access_token } = await login({ email, password })
      setToken(access_token)
      navigate('/dashboard')
    } catch (err) {
      setError(err.response?.data?.detail || 'Login failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div
      className="min-h-screen bg-white flex items-center justify-center"
      style={{
        backgroundImage: 'radial-gradient(circle, rgba(0,0,0,0.07) 1.5px, transparent 1.5px)',
        backgroundSize: '24px 24px',
      }}
    >
      <div className="bg-white border border-black/[0.08] rounded-xl shadow-card p-10 w-full max-w-sm">
        <div className="mb-8">
          <div className="w-8 h-8 bg-gray-900 rounded-lg mb-4" />
          <h1 className="text-xl font-sans font-semibold text-gray-900">Sign in</h1>
          <p className="text-sm text-gray-400 mt-1">QuantPortfolio</p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="text-[11px] font-sans font-semibold tracking-[0.12em] uppercase text-gray-400 block mb-1.5">
              Email
            </label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="w-full px-3 py-2 text-sm font-mono border border-black/[0.1] rounded-lg outline-none focus:border-gray-900 transition-colors"
            />
          </div>
          <div>
            <label className="text-[11px] font-sans font-semibold tracking-[0.12em] uppercase text-gray-400 block mb-1.5">
              Password
            </label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="w-full px-3 py-2 text-sm font-mono border border-black/[0.1] rounded-lg outline-none focus:border-gray-900 transition-colors"
            />
          </div>

          {error && <p className="text-xs font-mono text-red-600">{error}</p>}

          <button
            type="submit"
            disabled={loading}
            className="w-full py-2.5 bg-gray-900 text-white text-sm font-sans font-semibold rounded-lg hover:bg-gray-800 active:scale-[0.98] transition-all disabled:opacity-50"
          >
            {loading ? 'Signing in...' : 'Sign in'}
          </button>
        </form>

        <p className="text-xs text-gray-400 text-center mt-6">
          No account?{' '}
          <Link to="/register" className="text-gray-900 font-medium hover:underline">
            Register
          </Link>
        </p>
      </div>
    </div>
  )
}
