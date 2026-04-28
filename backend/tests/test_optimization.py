import numpy as np
import pytest


pytest.importorskip("cvxpy")

from backend.quant.black_litterman import BLInputs, black_litterman_returns, implied_equilibrium_returns
from backend.quant.mvo import constrained_mvo
from backend.schemas.optimization import PortfolioConstraints


def test_black_litterman_without_views_returns_equilibrium() -> None:
    cov = np.array([[0.10, 0.02], [0.02, 0.08]])
    weights = np.array([0.5, 0.5])
    inputs = BLInputs(
        cov=cov,
        market_weights=weights,
        risk_aversion=2.5,
        tau=0.025,
        P=None,
        Q=None,
        Omega=None,
    )

    posterior = black_litterman_returns(inputs)
    equilibrium = implied_equilibrium_returns(cov, weights, 2.5)
    assert np.allclose(posterior, equilibrium)


def test_constrained_mvo_respects_asset_class_bounds() -> None:
    mu = np.array([0.14, 0.08, 0.06])
    cov = np.array(
        [
            [0.05, 0.01, 0.00],
            [0.01, 0.04, 0.00],
            [0.00, 0.00, 0.02],
        ]
    )
    constraints = PortfolioConstraints.model_validate(
        {
            "stocks": {"min": 0.20, "max": 0.60},
            "crypto": {"min": 0.0, "max": 0.20},
            "gold": {"min": 0.0, "max": 0.20},
            "mf_etf": {"min": 0.0, "max": 0.20},
            "bonds": {"min": 0.20, "max": 0.80},
        }
    )

    weights = constrained_mvo(
        mu=mu,
        cov=cov,
        tickers=["AAA", "BBB", "CCC"],
        asset_classes=["stock", "crypto", "bond"],
        constraints=constraints,
        risk_tolerance=0.6,
    )

    assert pytest.approx(sum(weights.values()), rel=1e-6) == 1.0
    assert weights["AAA"] >= 0.20
    assert weights["AAA"] <= 0.60
    assert weights["BBB"] <= 0.20
    assert weights["CCC"] >= 0.20
