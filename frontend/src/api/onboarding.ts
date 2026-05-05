import client from './client'

export type InvestorProfilePayload = {
  investment_amount: number
  investment_horizon: 'short_term' | 'medium_term' | 'long_term'
  risk_appetite: 'conservative' | 'moderate' | 'aggressive'
  income_stability: 'stable' | 'variable'
  existing_investments: boolean
  age_group: '18-25' | '26-35' | '36-50' | '50+'
}

export type InvestorProfileResponse = InvestorProfilePayload & {
  id: string
  user_id: string
  risk_score: number
  created_at: string | null
  updated_at: string | null
}

export type PortfolioRecommendation = {
  ticker: string
  asset_class: string
  recommended_weight: number
  recommended_amount_inr: number
  current_price_inr: number | null
}

export const submitInvestorProfile = (payload: InvestorProfilePayload) =>
  client.post('/api/v1/onboarding/profile', payload).then((response) => response.data as InvestorProfileResponse)

export const getPortfolioRecommendation = () =>
  client.post('/api/v1/onboarding/recommend').then((response) => response.data as PortfolioRecommendation[])