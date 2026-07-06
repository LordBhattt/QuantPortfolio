"""Institutional covariance estimation and regime scaling.

Provides:
1. Ledoit-Wolf shrinkage (default, optimal for moderate sample sizes)
2. Exponentially weighted (responsive to regime changes)
3. Sample covariance (fallback)

Plus:
- Volatility shrinkage (smooth caps instead of hard clips)
- Regime-aware covariance scaling
- PSD enforcement throughout
- Correlation stabilisation
"""

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf


# ── Target volatilities for shrinkage (annualised) ───────────────────
# Instead of hard-capping vol, we shrink toward these targets.
# sigma_adj = alpha * sigma_raw + (1-alpha) * sigma_target
# This is smoother than hard clipping and preserves covariance structure.
ASSET_CLASS_TARGET_VOL: dict[str, float] = {
    "crypto": 0.55,
    "stock":  0.22,
    "mf_etf": 0.18,
    "gold":   0.15,
    "bond":   0.06,
}

# Shrinkage intensity per asset class (higher = more shrinkage)
VOL_SHRINKAGE_ALPHA: dict[str, float] = {
    "crypto": 0.45,   # crypto shrinks most toward target
    "stock":  0.70,   # stocks keep most of their raw vol
    "mf_etf": 0.75,
    "gold":   0.75,
    "bond":   0.80,
}


def compute_covariance(
    returns: pd.DataFrame,
    method: str = "ledoit_wolf",
    annualise: bool = True,
    trading_days: int = 252,
) -> np.ndarray:
    if returns.empty or len(returns.columns) == 0:
        raise ValueError("returns matrix is empty")
    if len(returns) < 2:
        raise ValueError("at least two return observations are required")

    if method == "ewm":
        cov = _ewm_covariance(returns, span=60)
    elif method == "ledoit_wolf":
        estimator = LedoitWolf().fit(returns.values)
        cov = estimator.covariance_
    else:
        cov = returns.cov().values

    if annualise:
        cov = cov * trading_days

    return _ensure_psd(cov)


def _ewm_covariance(returns: pd.DataFrame, span: int = 60) -> np.ndarray:
    """Exponentially weighted covariance (half-life ≈ span/2)."""
    ewm_cov = returns.ewm(span=span, min_periods=max(20, span // 3)).cov()
    last_date = returns.index[-1]
    cov = ewm_cov.loc[last_date].values
    n = len(returns.columns)
    return cov.reshape(n, n)


def shrink_volatility(
    cov: np.ndarray,
    asset_classes: list[str],
    annualised: bool = True,
    trading_days: int = 252,
) -> np.ndarray:
    """Shrink per-asset volatility toward asset-class target.

    Instead of hard clipping (which distorts the correlation structure),
    this applies:
        σ_adj = α·σ_raw + (1-α)·σ_target

    Then rescales the covariance row/column to match the new vol
    while preserving correlations exactly.
    """
    shrunk = cov.copy()
    n = cov.shape[0]

    for i in range(n):
        cls = asset_classes[i] if i < len(asset_classes) else "stock"
        target_vol = ASSET_CLASS_TARGET_VOL.get(cls, 0.25)
        alpha = VOL_SHRINKAGE_ALPHA.get(cls, 0.70)

        raw_var = shrunk[i, i]
        raw_vol = np.sqrt(raw_var)

        if annualised:
            target_var = target_vol ** 2
        else:
            target_var = (target_vol ** 2) / trading_days

        target_vol_daily = np.sqrt(target_var)

        # Shrink: blend raw vol toward target
        shrunk_vol = alpha * raw_vol + (1.0 - alpha) * target_vol_daily

        # Rescale row/column to match new vol while preserving correlation
        if raw_vol > 1e-12:
            ratio = shrunk_vol / raw_vol
            shrunk[i, :] *= ratio
            shrunk[:, i] *= ratio
            # The diagonal was scaled twice, correct it
            shrunk[i, i] = shrunk_vol ** 2

    return _ensure_psd(shrunk)


def scale_covariance_by_regime(
    cov: np.ndarray,
    regime_state: int | None = None,
    diag_scale: float = 1.0,
    offdiag_scale: float = 1.0,
    n_regimes: int = 3,
) -> np.ndarray:
    """Scale covariance using regime-specific multipliers.

    If regime_state is provided and scales are default, uses built-in map.
    Otherwise uses explicit scale parameters.
    """
    del n_regimes

    if regime_state is not None and diag_scale == 1.0 and offdiag_scale == 1.0:
        diag_map = {0: 0.85, 1: 1.0, 2: 1.40}
        offdiag_map = {0: 0.80, 1: 1.0, 2: 1.50}
        diag_scale = diag_map.get(regime_state, 1.0)
        offdiag_scale = offdiag_map.get(regime_state, 1.0)

    scaled = cov.copy()
    n = cov.shape[0]
    for i in range(n):
        for j in range(n):
            if i == j:
                scaled[i, j] *= diag_scale
            else:
                scaled[i, j] *= offdiag_scale

    return _ensure_psd(scaled)


# ── Legacy alias for backward compatibility ──
def dampen_crypto_volatility(
    cov: np.ndarray,
    asset_classes: list[str],
    annualised: bool = True,
    trading_days: int = 252,
) -> np.ndarray:
    """Legacy wrapper — now delegates to shrink_volatility."""
    return shrink_volatility(cov, asset_classes, annualised, trading_days)


def compute_correlation_matrix(cov: np.ndarray) -> np.ndarray:
    """Extract correlation matrix from covariance, handling zero-vol."""
    d = np.sqrt(np.diag(cov))
    d = np.where(d > 1e-12, d, 1.0)
    return cov / np.outer(d, d)


def _ensure_psd(matrix: np.ndarray, min_eigenvalue: float = 1e-8) -> np.ndarray:
    """Enforce positive semi-definiteness."""
    eigenvalues = np.linalg.eigvalsh(matrix)
    if np.any(eigenvalues < 0):
        matrix = matrix + (-eigenvalues.min() + min_eigenvalue) * np.eye(matrix.shape[0])
    return matrix
