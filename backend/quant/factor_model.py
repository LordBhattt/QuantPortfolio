"""Fama-French 5-factor regression."""

import uuid

import numpy as np
import pandas as pd

from backend.schemas.analytics import FactorExposure


def fama_french_regression(
    portfolio_returns: pd.Series,
    ff5_factors: pd.DataFrame,
    portfolio_id: uuid.UUID,
) -> FactorExposure:
    try:
        import statsmodels.api as sm
    except ImportError as exc:
        raise RuntimeError("statsmodels is required for factor decomposition") from exc

    aligned = pd.concat([portfolio_returns.rename("portfolio"), ff5_factors], axis=1).dropna()
    if aligned.empty:
        raise ValueError("insufficient overlap between portfolio returns and factor data")

    excess_returns = aligned["portfolio"] - aligned["RF"]
    X = aligned[["Mkt-RF", "SMB", "HML", "RMW", "CMA"]]
    X = sm.add_constant(X)
    model = sm.OLS(excess_returns, X).fit()

    return FactorExposure(
        portfolio_id=portfolio_id,
        alpha=float(model.params["const"]) * 252.0,
        beta_market=float(model.params["Mkt-RF"]),
        beta_smb=float(model.params["SMB"]),
        beta_hml=float(model.params["HML"]),
        beta_rmw=float(model.params["RMW"]),
        beta_cma=float(model.params["CMA"]),
        r_squared=float(model.rsquared),
        residual_std=float(model.resid.std()) * np.sqrt(252.0),
    )
