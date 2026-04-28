"""Covariance estimation and regime scaling."""

import numpy as np
import pandas as pd
from sklearn.covariance import LedoitWolf


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

    if method == "ledoit_wolf":
        estimator = LedoitWolf().fit(returns.values)
        cov = estimator.covariance_
    else:
        cov = returns.cov().values

    if annualise:
        cov = cov * trading_days
    return cov


def scale_covariance_by_regime(cov: np.ndarray, regime: int, n_regimes: int = 3) -> np.ndarray:
    del n_regimes
    scale_map = {0: 0.85, 1: 1.0, 2: 1.40}
    offdiag_extra = {0: 0.9, 1: 1.0, 2: 1.25}

    diag_scale = scale_map.get(regime, 1.0)
    offdiag_scale = diag_scale * offdiag_extra.get(regime, 1.0)

    scaled = cov.copy()
    n_assets = cov.shape[0]
    for row in range(n_assets):
        for col in range(n_assets):
            if row == col:
                scaled[row, col] *= diag_scale
            else:
                scaled[row, col] *= offdiag_scale

    eigenvalues = np.linalg.eigvalsh(scaled)
    if np.any(eigenvalues < 0):
        scaled += (-eigenvalues.min() + 1e-8) * np.eye(n_assets)
    return scaled
