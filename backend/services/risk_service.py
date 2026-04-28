import asyncio
from uuid import UUID

import numpy as np
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.errors import AppError
from backend.quant.covariance import compute_covariance
from backend.quant.data_fetcher import DataFetcher
from backend.quant.monte_carlo import simulate_portfolio
from backend.quant.risk_engine import (
    beta,
    calmar_ratio,
    historical_cvar,
    historical_var,
    max_drawdown,
    sharpe_ratio,
    sortino_ratio,
)
from backend.quant.returns import align_returns, log_returns
from backend.schemas.risk import MonteCarloResult, RiskMetrics
from backend.services.portfolio_service import load_portfolio_snapshot

settings = get_settings()


async def compute_risk_metrics(
    portfolio_id: UUID,
    user_id: UUID,
    db: AsyncSession,
    fetcher: DataFetcher,
) -> RiskMetrics:
    loop = asyncio.get_running_loop()
    _, holdings, assets = await load_portfolio_snapshot(portfolio_id, user_id, db)
    if not holdings:
        raise AppError("Risk computation failed", "empty_portfolio", "Portfolio has no holdings", 400)

    asset_map = {row["ticker"]: row for row in assets}
    tickers = [row["ticker"] for row in holdings if row["ticker"] in asset_map]
    quantities = {row["ticker"]: float(row["quantity"]) for row in holdings}
    asset_currencies = {ticker: asset_map[ticker]["currency"] for ticker in tickers}

    price_frames = await asyncio.gather(
        *[fetcher.get_price_history(ticker, asset_map[ticker]["data_source"], days=365) for ticker in tickers]
    )
    price_data = dict(zip(tickers, price_frames))
    usd_inr = await fetcher.get_usd_inr_rate()

    returns_df = await loop.run_in_executor(None, align_returns, price_data, asset_currencies, "USD", usd_inr)
    if returns_df.empty:
        raise AppError("Risk computation failed", "insufficient_returns", "Unable to compute portfolio returns", 400)

    current_values = {
        ticker: float(price_data[ticker]["close"].iloc[-1])
        * quantities[ticker]
        * (1.0 / usd_inr if asset_currencies[ticker].upper() == "INR" else 1.0)
        for ticker in tickers
    }
    total_value = float(sum(current_values.values()))
    total_value_inr = total_value * usd_inr
    if total_value <= 0:
        raise AppError("Risk computation failed", "invalid_portfolio_value", "Portfolio value must be positive", 400)

    common_tickers = [ticker for ticker in tickers if ticker in returns_df.columns]
    weights = np.array([current_values[ticker] / total_value for ticker in common_tickers])
    portfolio_returns = returns_df[common_tickers] @ weights

    benchmark_frame = await fetcher.get_price_history("SPY", "yahoo", days=365)
    benchmark_returns = log_returns(benchmark_frame["close"])
    aligned = pd.concat([portfolio_returns.rename("portfolio"), benchmark_returns.rename("benchmark")], axis=1).dropna()

    correlation_matrix = returns_df[common_tickers].corr().to_dict()
    var_95 = historical_var(portfolio_returns, 0.95) * total_value_inr
    var_99 = historical_var(portfolio_returns, 0.99) * total_value_inr
    cvar_95 = historical_cvar(portfolio_returns, 0.95) * total_value_inr
    cvar_99 = historical_cvar(portfolio_returns, 0.99) * total_value_inr

    return RiskMetrics(
        portfolio_id=portfolio_id,
        usd_inr_rate=float(usd_inr),
        var_95=float(var_95),
        var_99=float(var_99),
        cvar_95=float(cvar_95),
        cvar_99=float(cvar_99),
        max_drawdown=max_drawdown(portfolio_returns),
        sharpe_ratio=sharpe_ratio(portfolio_returns),
        sortino_ratio=sortino_ratio(portfolio_returns),
        calmar_ratio=calmar_ratio(portfolio_returns),
        annualised_return=float(portfolio_returns.mean() * 252),
        annualised_volatility=float(portfolio_returns.std() * np.sqrt(252)),
        beta=beta(aligned["portfolio"], aligned["benchmark"]) if not aligned.empty else 1.0,
        correlation_matrix=correlation_matrix,
    )


async def run_monte_carlo(
    portfolio_id: UUID,
    user_id: UUID,
    db: AsyncSession,
    fetcher: DataFetcher,
    n_paths: int | None = None,
    horizon_days: int | None = None,
) -> MonteCarloResult:
    loop = asyncio.get_running_loop()
    _, holdings, assets = await load_portfolio_snapshot(portfolio_id, user_id, db)
    if not holdings:
        raise AppError("Monte Carlo failed", "empty_portfolio", "Portfolio has no holdings", 400)

    asset_map = {row["ticker"]: row for row in assets}
    tickers = [row["ticker"] for row in holdings if row["ticker"] in asset_map]
    quantities = {row["ticker"]: float(row["quantity"]) for row in holdings}
    asset_currencies = {ticker: asset_map[ticker]["currency"] for ticker in tickers}

    price_frames = await asyncio.gather(
        *[fetcher.get_price_history(ticker, asset_map[ticker]["data_source"], days=365) for ticker in tickers]
    )
    price_data = dict(zip(tickers, price_frames))
    usd_inr = await fetcher.get_usd_inr_rate()
    returns_df = await loop.run_in_executor(None, align_returns, price_data, asset_currencies, "USD", usd_inr)
    if returns_df.empty:
        raise AppError("Monte Carlo failed", "insufficient_returns", "Unable to compute portfolio returns", 400)

    common_tickers = [ticker for ticker in tickers if ticker in returns_df.columns]
    current_values = {
        ticker: float(price_data[ticker]["close"].iloc[-1])
        * quantities[ticker]
        * (1.0 / usd_inr if asset_currencies[ticker].upper() == "INR" else 1.0)
        for ticker in common_tickers
    }
    total_value = float(sum(current_values.values()))
    if total_value <= 0:
        raise AppError("Monte Carlo failed", "invalid_portfolio_value", "Portfolio value must be positive", 400)

    weights = np.array([current_values[ticker] / total_value for ticker in common_tickers])
    mu_daily = returns_df[common_tickers].mean().values
    cov_daily = await loop.run_in_executor(None, compute_covariance, returns_df[common_tickers], "ledoit_wolf", False, 252)

    result = await loop.run_in_executor(
        None,
        simulate_portfolio,
        weights,
        mu_daily,
        cov_daily,
        total_value * usd_inr,
        n_paths or settings.MONTE_CARLO_PATHS,
        horizon_days or settings.MONTE_CARLO_HORIZON_DAYS,
    )
    return MonteCarloResult(
        portfolio_id=portfolio_id,
        usd_inr_rate=float(usd_inr),
        horizon_days=result["horizon_days"],
        paths=n_paths or settings.MONTE_CARLO_PATHS,
        percentiles=result["percentiles"],
        prob_loss=result["prob_loss"],
        expected_terminal_value=result["expected_terminal_value"],
        initial_value=result["initial_value"],
    )
