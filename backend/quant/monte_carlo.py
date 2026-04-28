"""Correlated Monte Carlo portfolio simulation."""

import numpy as np

from backend.config import get_settings

settings = get_settings()


def simulate_portfolio(
    weights: np.ndarray,
    mu: np.ndarray,
    cov: np.ndarray,
    initial_value: float,
    n_paths: int | None = None,
    horizon_days: int | None = None,
) -> dict:
    paths = n_paths or settings.MONTE_CARLO_PATHS
    horizon = horizon_days or settings.MONTE_CARLO_HORIZON_DAYS
    n_assets = len(weights)
    try:
        chol = np.linalg.cholesky(cov)
    except np.linalg.LinAlgError:
        chol = np.linalg.cholesky(cov + 1e-8 * np.eye(n_assets))

    all_paths = np.zeros((paths, horizon))
    terminal = np.zeros(paths)

    for path_index in range(paths):
        random_draws = np.random.standard_normal((horizon, n_assets))
        correlated = random_draws @ chol.T
        asset_returns = mu + correlated
        portfolio_returns = asset_returns @ weights
        values = initial_value * np.exp(np.cumsum(portfolio_returns))
        all_paths[path_index] = values
        terminal[path_index] = values[-1]

    percentiles = {
        label: np.percentile(all_paths, percentile, axis=0).tolist()
        for label, percentile in (("p5", 5), ("p25", 25), ("p50", 50), ("p75", 75), ("p95", 95))
    }
    return {
        "horizon_days": horizon,
        "percentiles": percentiles,
        "prob_loss": float(np.mean(terminal < initial_value)),
        "expected_terminal_value": float(terminal.mean()),
        "initial_value": float(initial_value),
    }
