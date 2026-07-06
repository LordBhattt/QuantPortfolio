"""Institutional-grade expected return engine.

Blends four return signals into a unified expected return vector:

    μ_final = w₁·Π_eq + w₂·μ_hist + w₃·μ_ML + w₄·μ_views

where the weights (w₁..w₄) are dynamically calibrated based on:
    - regime state (bull/sideways/bear)
    - market volatility level
    - forecast confidence
    - data quality

Key design principles:
    - Equilibrium-anchored: BL implied returns Π = δΣw_mkt serve as
      the gravitational center. All other signals pull away from this
      center, but only proportionally to their confidence.
    - Mean-reverting: Historical extremes are pulled toward long-term
      priors, preventing a single bearish year from dominating.
    - Regime-aware: Bull regimes tilt toward momentum; bear regimes
      tilt toward defensive priors; sideways trusts equilibrium most.
    - Non-negative for diversified portfolios: A balanced portfolio
      should NOT have structurally negative drift in neutral markets.
"""

import numpy as np
import pandas as pd

# ── Long-term nominal return priors (annualised, INR) ────────────────
ASSET_CLASS_ANNUAL_PRIOR: dict[str, float] = {
    "stock":  0.11,   # Nifty 50 long-run CAGR
    "mf_etf": 0.10,   # Diversified equity ETF
    "bond":   0.065,  # Indian G-Sec / liquid funds
    "gold":   0.09,   # INR gold long-run
    "crypto": 0.08,   # Conservative crypto prior
}
DEFAULT_PRIOR = 0.08


# ── Regime-dependent blending profiles ───────────────────────────────
# Each profile defines (w_equil, w_hist, w_ml, w_views) and a risk
# aversion multiplier for the BL equilibrium.

REGIME_PROFILES = {
    # Bull: trust momentum + ML more, lower risk aversion
    0: {
        "label": "bull",
        "weights": {"equilibrium": 0.30, "historical": 0.30, "ml": 0.25, "views": 0.15},
        "risk_aversion_mult": 0.80,   # lower → higher implied returns
        "shrinkage_strength": 0.40,   # less shrinkage, trust data more
        "vol_scale": 0.90,            # dampen vol slightly
    },
    # Sideways: equilibrium-dominated, stable
    1: {
        "label": "sideways",
        "weights": {"equilibrium": 0.50, "historical": 0.20, "ml": 0.15, "views": 0.15},
        "risk_aversion_mult": 1.00,
        "shrinkage_strength": 0.65,
        "vol_scale": 1.00,
    },
    # Bear: defensive priors, strong shrinkage, high risk aversion
    2: {
        "label": "bear",
        "weights": {"equilibrium": 0.50, "historical": 0.15, "ml": 0.10, "views": 0.25},
        "risk_aversion_mult": 1.30,   # higher → lower implied returns
        "shrinkage_strength": 0.70,
        "vol_scale": 1.25,
    },
}


def compute_equilibrium_returns(
    cov: np.ndarray,
    market_weights: np.ndarray,
    risk_aversion: float = 2.5,
    risk_free_rate: float = 0.065,
) -> np.ndarray:
    """Black-Litterman implied equilibrium returns (arithmetic).

    Π_log = δΣw_mkt   (excess log return in BL theory)

    Convert to arithmetic expected return:
        μ_arith = Π_log + Rf + 0.5σ²

    The 0.5σ² (Jensen's term) ensures that when Monte Carlo applies
    its own Itô correction (subtracting 0.5σ²), the net log-drift
    equals Π_log + Rf, which is positive for any reasonable portfolio.

    Without this conversion, the Itô correction in MC double-subtracts
    the variance term, causing structurally negative drift.
    """
    pi_log_excess = risk_aversion * cov @ market_weights
    sigma_sq = np.diag(cov)
    return pi_log_excess + risk_free_rate + 0.5 * sigma_sq


def compute_historical_returns(
    returns_df: pd.DataFrame,
    asset_classes: list[str],
    shrinkage_strength: float = 0.55,
) -> np.ndarray:
    """Bayesian-shrunk historical returns with Jensen's correction.

    Steps:
        1. Compute daily log-return means
        2. Add Jensen's correction: μ_arith = μ_log + 0.5σ²
        3. Annualise: R = μ_daily × 252
        4. Shrink toward long-term priors
        5. Convert back to daily
    """
    n_obs = len(returns_df)
    mu_log_daily = returns_df.mean().values
    var_daily = returns_df.var().values

    # Jensen's correction: log → arithmetic
    mu_arith_daily = mu_log_daily + 0.5 * var_daily

    # Annualise for shrinkage
    mu_annual = mu_arith_daily * 252

    # Long-term priors
    priors_annual = np.array([
        ASSET_CLASS_ANNUAL_PRIOR.get(cls, DEFAULT_PRIOR)
        for cls in asset_classes
    ])

    # Adaptive shrinkage: less data → more shrinkage
    data_confidence = min(1.0, n_obs / 504)  # 504 = 2 years
    alpha = np.clip(shrinkage_strength * (1.0 - 0.4 * data_confidence), 0.25, 0.80)

    # Bayesian blend
    mu_shrunk_annual = (1.0 - alpha) * mu_annual + alpha * priors_annual

    # Convert back to daily
    return mu_shrunk_annual / 252.0


def compute_momentum_adjustment(
    returns_df: pd.DataFrame,
    lookback_short: int = 21,
    lookback_long: int = 126,
    momentum_weight: float = 0.15,
) -> np.ndarray:
    """Momentum-adjusted drift based on trend persistence.

    If recent short-term returns are in the same direction as
    medium-term trend, momentum is positive → tilt drift up.
    If they diverge, mean-reversion dominates → tilt toward zero.
    """
    if len(returns_df) < lookback_long:
        return np.zeros(len(returns_df.columns))

    short_ret = returns_df.tail(lookback_short).mean().values * 252
    long_ret = returns_df.tail(lookback_long).mean().values * 252

    # Trend persistence: same sign = momentum, different = mean-reverting
    persistence = np.sign(short_ret) * np.sign(long_ret)
    momentum = np.where(
        persistence > 0,
        short_ret * momentum_weight,  # momentum: tilt in trend direction
        -short_ret * momentum_weight * 0.5,  # mean-reversion: partially reverse
    )
    # Cap momentum adjustment to ±3% annualised
    return np.clip(momentum, -0.03, 0.03) / 252.0


def blend_expected_returns(
    cov_annual: np.ndarray,
    market_weights: np.ndarray,
    returns_df: pd.DataFrame,
    asset_classes: list[str],
    regime_state: int = 1,
    ml_forecasts: np.ndarray | None = None,
    user_views: np.ndarray | None = None,
    base_risk_aversion: float = 2.5,
) -> tuple[np.ndarray, dict]:
    """Compute the final blended expected return vector.

    Returns
    -------
    mu_daily : (N,) daily expected return vector for each asset
    diagnostics : dict with component breakdowns for interpretability
    """
    profile = REGIME_PROFILES.get(regime_state, REGIME_PROFILES[1])
    n_assets = len(market_weights)

    # ── 1. Equilibrium returns (BL implied) ──
    risk_aversion = base_risk_aversion * profile["risk_aversion_mult"]
    pi_annual = compute_equilibrium_returns(cov_annual, market_weights, risk_aversion)
    pi_daily = pi_annual / 252.0

    # ── 2. Historical returns (Bayesian-shrunk) ──
    mu_hist_daily = compute_historical_returns(
        returns_df, asset_classes, profile["shrinkage_strength"],
    )

    # ── 3. ML forecasts (if available) ──
    if ml_forecasts is not None and len(ml_forecasts) == n_assets:
        mu_ml_daily = np.array(ml_forecasts, dtype=float) / 252.0
    else:
        mu_ml_daily = pi_daily  # fallback to equilibrium

    # ── 4. User views (if available) ──
    if user_views is not None and len(user_views) == n_assets:
        mu_views_daily = np.array(user_views, dtype=float) / 252.0
    else:
        mu_views_daily = pi_daily  # fallback to equilibrium

    # ── 5. Momentum adjustment ──
    momentum_adj = compute_momentum_adjustment(returns_df)
    if len(momentum_adj) != n_assets:
        momentum_adj = np.zeros(n_assets)

    # ── 6. Dynamic blending ──
    w = profile["weights"]
    mu_blended = (
        w["equilibrium"] * pi_daily
        + w["historical"] * mu_hist_daily
        + w["ml"] * mu_ml_daily
        + w["views"] * mu_views_daily
        + momentum_adj
    )

    # ── 7. Floor: Itô-aware per-asset floor ──
    # MC applies: log_drift = mu_arith - 0.5*σ²
    # For net log-drift ≥ scale*Rf, we need: mu_arith ≥ scale*Rf + 0.5*σ²
    # This is per-asset since each asset has different volatility.
    rf_daily = 0.065 / 252.0
    sigma_sq_daily = np.diag(cov_annual) / 252.0   # daily variance per asset
    if regime_state == 0:  # bull
        drift_floor = rf_daily * 1.0 + 0.5 * sigma_sq_daily
    elif regime_state == 1:  # sideways
        drift_floor = rf_daily * 0.6 + 0.5 * sigma_sq_daily
    else:  # bear
        drift_floor = rf_daily * 0.1 + 0.5 * sigma_sq_daily * 0.5
    mu_blended = np.maximum(mu_blended, drift_floor)

    diagnostics = {
        "regime": profile["label"],
        "risk_aversion": risk_aversion,
        "weights": w,
        "equilibrium_annual": (pi_daily * 252).tolist(),
        "historical_annual": (mu_hist_daily * 252).tolist(),
        "ml_annual": (mu_ml_daily * 252).tolist(),
        "blended_annual": (mu_blended * 252).tolist(),
        "momentum_annual": (momentum_adj * 252).tolist(),
    }

    return mu_blended, diagnostics


def compute_market_weights_from_volatility(
    cov: np.ndarray,
) -> np.ndarray:
    """Volatility-inverse market cap proxy.

    Lower-vol assets get higher weight (bonds, gold),
    higher-vol assets get lower weight (crypto).
    This mimics global market-cap weighting where stable
    asset classes represent larger share of total wealth.
    """
    vols = np.sqrt(np.diag(cov))
    if np.all(vols > 0):
        inv_vols = 1.0 / vols
        return inv_vols / inv_vols.sum()
    return np.ones(len(vols)) / len(vols)
