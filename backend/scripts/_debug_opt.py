"""Debug: run the full optimize pipeline with cached parquet data."""
import sys
sys.path.insert(0, 'd:/QuantPortfolio')

import numpy as np
import pandas as pd
from pathlib import Path

CACHE_DIR = Path('backend/data/cache')

# Map ticker -> parquet filename convention
def ticker_to_fname(ticker):
    return ticker.replace('.', '_').replace('-', '-')

def load_cached(ticker):
    stem = ticker.replace('.', '_')
    matches = list(CACHE_DIR.glob(f"{stem}_*.parquet"))
    if not matches:
        return None
    df = pd.read_parquet(matches[0])
    # Normalize columns to lowercase
    df.columns = [c.lower() for c in df.columns]
    df.index = pd.to_datetime(df.index)
    df = df.sort_index()
    return df

# Demo portfolio
tickers = ['RELIANCE.NS', 'BTC-USD', 'GLD', 'GOLDBEES.NS', 'NIFTYBEES.NS', 'HDFCBANK.NS', 'LTGILTDIR.NS', 'TCS.NS']
asset_classes = ['stock', 'crypto', 'gold', 'gold', 'mf_etf', 'stock', 'bond', 'stock']
currencies = ['INR', 'USD', 'USD', 'INR', 'INR', 'INR', 'INR', 'INR']

print("Loading cached price data...")
price_data = {}
for t in tickers:
    df = load_cached(t)
    if df is not None:
        print(f"  OK {t}: {len(df)} rows, cols={list(df.columns)[:4]}")
        price_data[t] = df
    else:
        print(f"  MISSING {t}")

usd_inr = 84.0  # approximate

from backend.quant.returns import align_returns

asset_currencies = dict(zip(tickers, currencies))
valid_tickers = list(price_data.keys())
valid_currencies = {t: asset_currencies[t] for t in valid_tickers}

returns_df = align_returns(price_data, valid_currencies, 'USD', usd_inr)
print(f"\nReturns shape: {returns_df.shape}")
print(f"Columns: {list(returns_df.columns)}")
print(f"Date range: {returns_df.index[0]} to {returns_df.index[-1]}")

if returns_df.empty:
    print("Returns EMPTY - cannot proceed")
    sys.exit(1)

valid_tickers_final = [t for t in valid_tickers if t in returns_df.columns]
valid_asset_classes = [asset_classes[tickers.index(t)] for t in valid_tickers_final]
print(f"\nValid tickers: {valid_tickers_final}")
print(f"Asset classes: {valid_asset_classes}")

from backend.quant.covariance import compute_covariance, shrink_volatility

cov = compute_covariance(returns_df[valid_tickers_final], 'ledoit_wolf', True, 252)
print(f"\nCov shape: {cov.shape}, finite: {np.all(np.isfinite(cov))}")
eigvals = np.linalg.eigvalsh(cov)
print(f"Cov eigenvalues: min={eigvals.min():.6f}, max={eigvals.max():.4f}")

cov_shrunk = shrink_volatility(cov, valid_asset_classes, True, 252)

from backend.quant.expected_returns import blend_expected_returns, compute_market_weights_from_volatility

market_weights = compute_market_weights_from_volatility(cov_shrunk)
mu_daily, diagnostics = blend_expected_returns(
    cov_annual=cov_shrunk,
    market_weights=market_weights,
    returns_df=returns_df[valid_tickers_final],
    asset_classes=valid_asset_classes,
    regime_state=1,
)
mu_annual = mu_daily * 252
print(f"\nmu_annual: {dict(zip(valid_tickers_final, mu_annual.round(4)))}")

from backend.quant.mvo import constrained_mvo
from backend.schemas.optimization import PortfolioConstraints

constraints = PortfolioConstraints(
    stocks={"min": 0.1, "max": 0.5},
    crypto={"min": 0.05, "max": 0.2},
    gold={"min": 0.05, "max": 0.2},
    bonds={"min": 0.1, "max": 0.3},
    mf_etf={"min": 0.05, "max": 0.3},
)

print("\nTrying MVO with constraints...")
try:
    result = constrained_mvo(
        mu=mu_annual,
        cov=cov_shrunk,
        tickers=valid_tickers_final,
        asset_classes=valid_asset_classes,
        constraints=constraints,
        risk_tolerance=0.5,
    )
    print("SUCCESS:", result)
except Exception as e:
    print(f"FAILED with constraints: {e}")
    print("Trying without constraints...")
    try:
        result2 = constrained_mvo(
            mu=mu_annual,
            cov=cov_shrunk,
            tickers=valid_tickers_final,
            asset_classes=valid_asset_classes,
            constraints=None,
            risk_tolerance=0.5,
        )
        print("Without constraints OK:", result2)
    except Exception as e2:
        print(f"ALSO FAILED without constraints: {e2}")
        print(f"mu range: {mu_annual.min():.6f} to {mu_annual.max():.6f}")
        print(f"cov diag: {np.diag(cov_shrunk)}")
