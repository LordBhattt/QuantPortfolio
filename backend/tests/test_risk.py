import numpy as np
import pandas as pd

from backend.quant.monte_carlo import simulate_portfolio
from backend.quant.risk_engine import historical_cvar, historical_var, max_drawdown


def test_historical_cvar_is_at_least_var() -> None:
    returns = pd.Series([-0.05, -0.03, -0.01, 0.01, 0.02, 0.03])
    var_95 = historical_var(returns, 0.95)
    cvar_95 = historical_cvar(returns, 0.95)
    assert cvar_95 >= var_95


def test_max_drawdown_is_non_positive() -> None:
    returns = pd.Series([0.05, -0.02, -0.04, 0.01, -0.01])
    drawdown = max_drawdown(returns)
    assert drawdown <= 0.0


def test_monte_carlo_returns_expected_shape() -> None:
    result = simulate_portfolio(
        weights=np.array([0.6, 0.4]),
        mu=np.array([0.0005, 0.0002]),
        cov=np.array([[0.0001, 0.0], [0.0, 0.00005]]),
        initial_value=1000.0,
        n_paths=100,
        horizon_days=20,
    )
    assert result["horizon_days"] == 20
    assert len(result["percentiles"]["p50"]) == 20
    assert result["initial_value"] == 1000.0
