"""Portfolio risk metrics.

All functions expect *daily log returns* (i.e. the output of
``np.log(p / p.shift(1))``).  Annualization is done correctly for
log returns using:

    annual_geometric_return = exp(daily_log_mean * 252) - 1
    annual_volatility       = daily_std * sqrt(252)
    annual_arithmetic_return = daily_log_mean * 252 + 0.5 * daily_var * 252
"""

import numpy as np
import pandas as pd

from backend.config import get_settings

settings = get_settings()


# ── Return annualisation helpers ─────────────────────────────────────

def _annualised_arithmetic_return(log_returns: pd.Series, trading_days: int = 252) -> float:
    """Convert daily log-return mean to annualised *arithmetic* return.

    arithmetic_annual = daily_log_mean * T + 0.5 * daily_variance * T

    This accounts for the Jensen's inequality gap between the mean of
    log returns and the expected simple return, which is critical for
    getting Sharpe ratios that match real-world interpretations.
    """
    mu_log = float(log_returns.mean())
    var_log = float(log_returns.var())
    return mu_log * trading_days + 0.5 * var_log * trading_days


def _annualised_geometric_return(log_returns: pd.Series, trading_days: int = 252) -> float:
    """Convert daily log-return mean to annualised *geometric* (CAGR-like) return."""
    return float(np.exp(log_returns.mean() * trading_days) - 1.0)


def _annualised_volatility(log_returns: pd.Series, trading_days: int = 252) -> float:
    return float(log_returns.std() * np.sqrt(trading_days))


# ── VaR / CVaR ───────────────────────────────────────────────────────

def historical_var(returns: pd.Series, confidence: float = 0.95) -> float:
    return float(-np.percentile(returns, (1.0 - confidence) * 100.0))


def historical_cvar(returns: pd.Series, confidence: float = 0.95) -> float:
    var = historical_var(returns, confidence)
    tail = returns[returns <= -var]
    return float(-tail.mean()) if len(tail) > 0 else var


# ── Drawdown ─────────────────────────────────────────────────────────

def max_drawdown(returns: pd.Series) -> float:
    cumulative = (1.0 + returns).cumprod()
    rolling_max = cumulative.cummax()
    drawdown = (cumulative - rolling_max) / rolling_max
    return float(drawdown.min())


# ── Sharpe / Sortino / Calmar ────────────────────────────────────────

def sharpe_ratio(returns: pd.Series, risk_free_rate: float | None = None, trading_days: int = 252) -> float:
    """Annualised Sharpe using arithmetic excess return.

    Sharpe = (R_arith_annual - Rf) / σ_annual

    where R_arith_annual is computed from log returns using the
    Jensen's-inequality correction (daily_log_mean*252 + 0.5*var*252).
    This ensures the Sharpe is not artificially depressed by the
    log-return bias.
    """
    rf = risk_free_rate if risk_free_rate is not None else settings.RISK_FREE_RATE
    r_annual = _annualised_arithmetic_return(returns, trading_days)
    vol_annual = _annualised_volatility(returns, trading_days)
    return float((r_annual - rf) / vol_annual) if vol_annual > 0 else 0.0


def sortino_ratio(returns: pd.Series, risk_free_rate: float | None = None, trading_days: int = 252) -> float:
    rf = risk_free_rate if risk_free_rate is not None else settings.RISK_FREE_RATE
    rf_daily = rf / trading_days
    excess = returns - rf_daily
    downside = excess[excess < 0]
    downside_std = np.sqrt((downside**2).mean()) if len(downside) > 0 else 0.0
    downside_annual = downside_std * np.sqrt(trading_days)
    r_annual = _annualised_arithmetic_return(returns, trading_days)
    return float((r_annual - rf) / downside_annual) if downside_annual > 0 else 0.0


def calmar_ratio(returns: pd.Series, trading_days: int = 252) -> float:
    annual_return = _annualised_arithmetic_return(returns, trading_days)
    drawdown = abs(max_drawdown(returns))
    return float(annual_return / drawdown) if drawdown > 0 else 0.0


# ── Beta ─────────────────────────────────────────────────────────────

def beta(portfolio_returns: pd.Series, market_returns: pd.Series) -> float:
    aligned = pd.concat([portfolio_returns.rename("portfolio"), market_returns.rename("market")], axis=1).dropna()
    if aligned.empty:
        return 1.0
    covariance = np.cov(aligned.values.T)
    market_variance = covariance[1, 1]
    return float(covariance[0, 1] / market_variance) if market_variance > 0 else 1.0
