import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useQueryClient } from '@tanstack/react-query'

import { register } from '../api/auth'
import { getApiErrorMessage } from '../api/client'
import AuroraBackground from '../components/ui-qp/AuroraBackground'
import Card from '../components/ui-qp/Card'
import Scene3D from '../components/ui-qp/Scene3D'
import { usePortfolioStore } from '../store/portfolioStore'

export default function Register() {
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const handleSubmit = async (e) => {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const user = await register({
        email: email.trim(),
        password,
        full_name: fullName || null,
      })
      queryClient.setQueryData(['current-user'], user)
      navigate(usePortfolioStore.getState().onboarded ? '/dashboard' : '/onboarding', { replace: true })
    } catch (err) {
      setError(getApiErrorMessage(err, 'Registration failed'))
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative min-h-screen bg-white flex items-center justify-center overflow-hidden">
      <AuroraBackground />

      <Scene3D className="pointer-events-none absolute right-[8%] top-1/2 hidden h-[380px] w-[380px] -translate-y-1/2 lg:block" />

      <div className="relative z-10 w-full max-w-sm animate-fadeUp opacity-0">
        <Card tilt hover={false} className="p-10">
          <div className="mb-8">
            <div className="w-8 h-8 bg-gray-900 rounded-lg mb-4 animate-float" />
            <h1 className="text-xl font-sans font-semibold text-gray-900">Create account</h1>
            <p className="text-sm text-gray-400 mt-1">QuantPortfolio</p>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="text-[11px] font-sans font-semibold tracking-[0.12em] uppercase text-gray-400 block mb-1.5">
                Full Name
              </label>
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="w-full px-3 py-2 text-sm font-mono border border-black/[0.1] rounded-lg outline-none focus:border-gray-900 focus:ring-2 focus:ring-primary/20 transition-all"
              />
            </div>
            <div>
              <label className="text-[11px] font-sans font-semibold tracking-[0.12em] uppercase text-gray-400 block mb-1.5">
                Email
              </label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                className="w-full px-3 py-2 text-sm font-mono border border-black/[0.1] rounded-lg outline-none focus:border-gray-900 focus:ring-2 focus:ring-primary/20 transition-all"
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
                minLength={8}
                className="w-full px-3 py-2 text-sm font-mono border border-black/[0.1] rounded-lg outline-none focus:border-gray-900 focus:ring-2 focus:ring-primary/20 transition-all"
              />
            </div>

            {error && <p className="text-xs font-mono text-red-600">{error}</p>}

            <button
              type="submit"
              disabled={loading}
              className="w-full py-2.5 bg-gray-900 text-white text-sm font-sans font-semibold rounded-lg hover:bg-gray-800 active:scale-[0.98] transition-all disabled:opacity-50"
            >
              {loading ? 'Creating account...' : 'Create account'}
            </button>
          </form>

          <p className="text-xs text-gray-400 text-center mt-6">
            Already have an account?{' '}
            <Link to="/login" className="text-gray-900 font-medium hover:underline">
              Sign in
            </Link>
          </p>
        </Card>
      </div>
    </div>
  )
}
