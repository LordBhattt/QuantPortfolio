"""Test original optimize with more debug info."""
import httpx
import json

c = httpx.Client(base_url='http://localhost:8000', timeout=60, follow_redirects=True)
c.post('/api/v1/auth/token', data={'username': 'demo@quantportfolio.in', 'password': 'Demo@1234'})

pid = 'cdf52c27-24af-4fb2-96d2-883390b7db52'

# Check what NIFTYBEES.NS looks like from price API
# First the original constraints test
r = c.post('/api/v1/optimize/', json={
    'portfolio_id': pid,
    'risk_tolerance': 0.5,
    'use_ml_forecast': False,
    'use_regime_scaling': False,
    # NO override - uses portfolio constraints: stocks 10-50, crypto 5-20, gold 5-20, bonds 10-30, mf_etf 5-30
})
print('Status:', r.status_code)
if r.status_code == 200:
    d = r.json()
    print('Weights:')
    for w in d.get('optimal_weights', []):
        print(f"  {w['ticker']:20} {w['weight']:.3f}")
elif r.status_code == 500:
    print('500 Error:', r.json())

# Try with constraints that explicitly allow any weight for any class (override)
r2 = c.post('/api/v1/optimize/', json={
    'portfolio_id': pid,
    'risk_tolerance': 0.5,
    'use_ml_forecast': False,
    'use_regime_scaling': False,
    'constraints': None,  # pass null to force no constraints
})
print('\nNo constraints, status:', r2.status_code)
if r2.status_code == 200:
    d = r2.json()
    print('Weights:')
    for w in d.get('optimal_weights', []):
        print(f"  {w['ticker']:20} {w['weight']:.3f}")
elif r2.status_code == 500:
    print('500 Error:', r2.json())
