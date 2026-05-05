import { Navigate } from 'react-router-dom'

import { useCurrentUser } from '../../hooks/useAuth'

export default function RequireAuth({ children }) {
  const { data: currentUser, loading } = useCurrentUser()
  if (loading) return null
  if (!currentUser) return <Navigate to="/login" replace />
  return children
}
