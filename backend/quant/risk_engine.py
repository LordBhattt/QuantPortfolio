"""Portfolio risk metrics."""

import numpy as np
import pandas as pd

from backend.config import get_settings

settings = get_settings()


def historical_var(returns: pd.Series, confidence: float = 0.95) -> float:
    return float(-np.percentile(returns, (1.0 - confidence) * 100.0))


def historical_cvar(returns: pd.Series, confidence: float = 0.95) -> float:
    var = historical_var(returns, confidence)
    tail = returns[returns <= -var]
    return float(-tail.mean()) if len(tail) > 0 else var


def max_drawdown(returns: pd.Series) -> float:
    cumulative = (1.0 + returns).cumprod()
    rolling_max = cumulative.cummax()
    drawdown = (cumulative - rolling_max) / rolling_max
    return float(drawdown.min())


def sharpe_ratio(returns: pd.Series, risk_free_rate: float | None = None, trading_days: int = 252) -> float:
    rf = (risk_free_rate if risk_free_rate is not None else settings.RISK_FREE_RATE) / trading_days
    excess = returns - rf
    std = excess.std()
    return float(excess.mean() / std * np.sqrt(trading_days)) if std > 0 else 0.0


def sortino_ratio(returns: pd.Series, risk_free_rate: float | None = None, trading_days: int = 252) -> float:
    rf = (risk_free_rate if risk_free_rate is not None else settings.RISK_FREE_RATE) / trading_days
    excess = returns - rf
    downside = excess[excess < 0]
    downside_std = np.sqrt((downside**2).mean())
    return float(excess.mean() / downside_std * np.sqrt(trading_days)) if downside_std > 0 else 0.0


def calmar_ratio(returns: pd.Series, trading_days: int = 252) -> float:
    annual_return = returns.mean() * trading_days
    drawdown = abs(max_drawdown(returns))
    return float(annual_return / drawdown) if drawdown > 0 else 0.0


def beta(portfolio_returns: pd.Series, market_returns: pd.Series) -> float:
    aligned = pd.concat([portfolio_returns.rename("portfolio"), market_returns.rename("market")], axis=1).dropna()
    if aligned.empty:
        return 1.0
    covariance = np.cov(aligned.values.T)
    market_variance = covariance[1, 1]
    return float(covariance[0, 1] / market_variance) if market_variance > 0 else 1.0
