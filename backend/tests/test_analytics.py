import numpy as np
import pandas as pd
import pytest


pytest.importorskip("statsmodels")

from backend.quant.factor_model import fama_french_regression


def test_fama_french_regression_returns_factor_exposure() -> None:
    index = pd.date_range("2024-01-01", periods=30, freq="B")
    portfolio_returns = pd.Series(np.random.normal(0.0005, 0.01, size=30), index=index)
    factors = pd.DataFrame(
        {
            "Mkt-RF": np.random.normal(0.0004, 0.008, size=30),
            "SMB": np.random.normal(0.0001, 0.004, size=30),
            "HML": np.random.normal(0.0001, 0.004, size=30),
            "RMW": np.random.normal(0.0001, 0.003, size=30),
            "CMA": np.random.normal(0.0001, 0.003, size=30),
            "RF": np.full(30, 0.0001),
        },
        index=index,
    )

    exposure = fama_french_regression(portfolio_returns, factors, portfolio_id="00000000-0000-0000-0000-000000000001")
    assert -1.0 <= exposure.r_squared <= 1.0
    assert isinstance(exposure.beta_market, float)
