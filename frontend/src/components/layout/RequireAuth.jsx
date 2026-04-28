import { Navigate } from 'react-router-dom'

import { usePortfolioStore } from '../../store/portfolioStore'

export default function RequireAuth({ children }) {
  const token = usePortfolioStore((s) => s.token)
  if (!token) return <Navigate to="/login" replace />
  return children
}
