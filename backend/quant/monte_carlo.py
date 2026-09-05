"""Institutional-grade Monte Carlo simulation engine.

Implements regime-switching GBM with:
    - Student-t innovations (fat tails, df=5)
    - Jump diffusion (rare crash events)
    - Regime-dependent drift and volatility
    - Proper Itô drift correction aligned with input convention
    - Correlated multi-asset paths via Cholesky

CRITICAL: mu is expected as daily ARITHMETIC return (not log return).
The Itô correction converts: log_drift = mu_arith - 0.5*σ²
The σ² used is the PORTFOLIO's own (diversified) simulation variance,
applied once at the portfolio level -- not each asset's individual
variance applied per-asset then weighted, which would ignore
diversification and tax the drift once per asset instead of once for
the portfolio as a whole.
"""

import hashlib

import numpy as np

from backend.config import get_settings

settings = get_settings()


def _build_seed(
    weights: np.ndarray, mu: np.ndarray, cov: np.ndarray,
    initial_value: float, paths: int, horizon: int,
) -> int:
    hasher = hashlib.sha256()
    hasher.update(np.asarray(weights, dtype=np.float64).round(8).tobytes())
    hasher.update(np.asarray(mu, dtype=np.float64).round(8).tobytes())
    hasher.update(np.asarray(cov, dtype=np.float64).round(8).tobytes())
    hasher.update(np.asarray([initial_value, paths, horizon], dtype=np.float64).round(8).tobytes())
    return int.from_bytes(hasher.digest()[:8], "big", signed=False) % (2**32)


# ── Long-term priors for Bayesian drift shrinkage ────────────────────
ASSET_CLASS_ANNUAL_PRIOR: dict[str, float] = {
    "stock":  0.11,
    "mf_etf": 0.10,
    "bond":   0.065,
    "gold":   0.09,
    "crypto": 0.08,
}
DEFAULT_PRIOR = 0.08


def bayesian_shrink_mu(
    mu_daily_sample: np.ndarray,
    asset_classes: list[str],
    n_observations: int,
    shrinkage_strength: float = 0.55,
) -> np.ndarray:
    """Shrink daily arithmetic mean toward long-term priors."""
    data_weight = min(1.0, n_observations / 504)
    alpha = np.clip(shrinkage_strength * (1.0 - 0.4 * data_weight), 0.25, 0.75)

    priors_annual = np.array([
        ASSET_CLASS_ANNUAL_PRIOR.get(cls, DEFAULT_PRIOR) for cls in asset_classes
    ])
    mu_prior_daily = priors_annual / 252.0

    return (1.0 - alpha) * mu_daily_sample + alpha * mu_prior_daily


def simulate_portfolio(
    weights: np.ndarray,
    mu: np.ndarray,
    cov: np.ndarray,
    initial_value: float,
    n_paths: int | None = None,
    horizon_days: int | None = None,
    regime_state: int = 1,
    use_student_t: bool = True,
    use_jumps: bool = True,
    t_df: float = 5.0,
    jump_intensity: float = 0.02,
    jump_mean: float = -0.03,
    jump_std: float = 0.04,
) -> dict:
    """Run regime-aware Monte Carlo with fat tails and jump diffusion.

    Parameters
    ----------
    weights        : (N,) portfolio weight vector
    mu             : (N,) per-asset daily *arithmetic* expected return
    cov            : (N,N) per-asset daily covariance matrix
    initial_value  : portfolio value in INR at t=0
    regime_state   : 0=bull, 1=sideways, 2=bear
    """
    paths = n_paths or settings.MONTE_CARLO_PATHS
    horizon = horizon_days or settings.MONTE_CARLO_HORIZON_DAYS
    n_assets = len(weights)

    # ── Regime-dependent parameter adjustments ──
    regime_drift_mult = {0: 1.10, 1: 1.00, 2: 0.75}
    regime_vol_mult = {0: 0.95, 1: 1.00, 2: 1.20}
    regime_jump_mult = {0: 0.5, 1: 1.0, 2: 1.8}

    drift_mult = regime_drift_mult.get(regime_state, 1.0)
    vol_mult = regime_vol_mult.get(regime_state, 1.0)
    jump_mult = regime_jump_mult.get(regime_state, 1.0)

    # Scale covariance by regime volatility
    cov_sim = cov * (vol_mult ** 2)

    # Ensure PSD
    try:
        chol = np.linalg.cholesky(cov_sim)
    except np.linalg.LinAlgError:
        cov_sim += 1e-8 * np.eye(n_assets)
        chol = np.linalg.cholesky(cov_sim)

    seed = _build_seed(weights, mu, cov, initial_value, paths, horizon)
    rng = np.random.default_rng(seed)

    # ── CRITICAL: Correct Itô drift ──
    # mu is daily arithmetic return. For GBM log-return simulation:
    #   log_return = (mu_arith - 0.5 * sigma_actual²) + sigma_actual * Z
    #
    # sigma_actual² must match what the simulation ACTUALLY produces for
    # the PORTFOLIO's value process, which depends on whether we use
    # Student-t or Gaussian (both scaled to unit variance, so the
    # portfolio's simulated variance equals its Cholesky-derived
    # port_vol_sq below regardless of the innovation distribution).
    #
    # Portfolio-level parameters. port_vol_sq is the *diversified*
    # portfolio variance (w' Σ w), computed once via the Cholesky
    # factor -- this must be what gets subtracted, not the weighted
    # sum of each asset's own undiversified variance, or diversification
    # benefit is lost and a small allocation to a high-vol asset (e.g.
    # crypto) tanks the whole portfolio's drift disproportionately.
    mu_adjusted = mu * drift_mult
    port_chol_row = chol.T @ weights
    port_vol_sq = float(port_chol_row @ port_chol_row)
    port_drift = float(mu_adjusted @ weights) - 0.5 * port_vol_sq

    # ── Vectorised simulation ──
    all_paths = np.empty((paths, horizon))

    for p in range(paths):
        if use_student_t and t_df > 2:
            # Student-t innovations scaled to unit variance
            z_raw = rng.standard_t(df=t_df, size=(horizon, n_assets))
            # Var(standard_t) = df/(df-2), so scale to unit variance
            scale_factor = np.sqrt((t_df - 2.0) / t_df)
            z = z_raw * scale_factor
        else:
            z = rng.standard_normal((horizon, n_assets))

        # Correlated portfolio log-returns
        port_log_returns = port_drift + z @ port_chol_row

        # ── Jump diffusion (Merton model) ──
        if use_jumps:
            effective_intensity = jump_intensity * jump_mult
            n_jumps = rng.poisson(effective_intensity, size=horizon)
            jump_mask = n_jumps > 0
            if np.any(jump_mask):
                jump_returns = np.zeros(horizon)
                jump_returns[jump_mask] = (
                    rng.normal(jump_mean, jump_std, size=int(jump_mask.sum()))
                    * n_jumps[jump_mask]
                )
                port_log_returns += jump_returns

        # Compound to price path
        values = initial_value * np.exp(np.cumsum(port_log_returns))
        all_paths[p] = values

    terminal = all_paths[:, -1]

    percentiles = {
        label: np.percentile(all_paths, pct, axis=0).tolist()
        for label, pct in (("p5", 5), ("p25", 25), ("p50", 50), ("p75", 75), ("p95", 95))
    }

    return {
        "horizon_days": horizon,
        "percentiles": percentiles,
        "prob_loss": float(np.mean(terminal < initial_value)),
        "expected_terminal_value": float(terminal.mean()),
        "initial_value": float(initial_value),
        "regime": {0: "bull", 1: "sideways", 2: "bear"}.get(regime_state, "sideways"),
        "median_annual_return": float(
            (np.median(terminal) / initial_value) ** (252.0 / max(horizon, 1)) - 1.0
        ),
    }
