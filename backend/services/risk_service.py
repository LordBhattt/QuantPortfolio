"""Risk service — integrates regime detection, expected returns, and Monte Carlo.

Pipeline:
    1. Load holdings + fetch prices
    2. Compute log returns
    3. Detect market regime (HMM + vol + trend)
    4. Build regime-aware expected returns
    5. Estimate covariance with volatility shrinkage
    6. Run regime-switching Monte Carlo
    7. Compute risk metrics (VaR, CVaR, Sharpe, etc.)
"""

import asyncio
from uuid import UUID

import numpy as np
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.errors import AppError
from backend.quant.covariance import compute_covariance, shrink_volatility
from backend.quant.data_fetcher import DataFetcher
from backend.quant.expected_returns import (
    blend_expected_returns,
    compute_market_weights_from_volatility,
)
from backend.quant.monte_carlo import bayesian_shrink_mu, simulate_portfolio
from backend.quant.regime import RegimeDetector, RegimeState
from backend.quant.risk_engine import (
    _annualised_arithmetic_return,
    _annualised_volatility,
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

# Module-level regime detector reference (set by optimization_service.init_ml_models)
_regime_detector: RegimeDetector | None = None


def set_regime_detector(detector: RegimeDetector) -> None:
    global _regime_detector
    _regime_detector = detector


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

    price_results = await asyncio.gather(
        *[fetcher.get_price_history(ticker, asset_map[ticker]["data_source"], days=365) for ticker in tickers],
        return_exceptions=True,
    )
    price_data = {
        ticker: frame
        for ticker, frame in zip(tickers, price_results)
        if not isinstance(frame, Exception) and not frame.empty
    }
    usd_inr = await fetcher.get_usd_inr_rate()
    live_prices_inr = (
        await fetcher.get_latest_prices_in_inr(
            [
                {
                    "ticker": ticker,
                    "source": asset_map[ticker]["data_source"],
                    "exchange": asset_map[ticker].get("exchange"),
                    "currency": asset_currencies[ticker],
                }
                for ticker in tickers
            ]
        )
        if hasattr(fetcher, "get_latest_prices_in_inr")
        else {}
    )

    returns_df = await loop.run_in_executor(None, align_returns, price_data, asset_currencies, "USD", usd_inr)
    current_values: dict[str, float] = {}
    for ticker in tickers:
        live_price_inr = live_prices_inr.get(ticker)
        if live_price_inr is not None:
            current_values[ticker] = float(live_price_inr * quantities[ticker] / usd_inr)
            continue
        frame = price_data.get(ticker)
        if frame is None or frame.empty:
            continue
        current_values[ticker] = (
            float(frame["close"].iloc[-1])
            * quantities[ticker]
            * (1.0 / usd_inr if asset_currencies[ticker].upper() == "INR" else 1.0)
        )
    total_value = float(sum(current_values.values()))
    total_value_inr = total_value * usd_inr
    if total_value <= 0:
        raise AppError("Risk computation failed", "invalid_portfolio_value", "Portfolio value must be positive", 400)

    common_tickers = [ticker for ticker in current_values if ticker in returns_df.columns]
    if returns_df.empty or not common_tickers:
        return _neutral_risk_metrics(portfolio_id, usd_inr)

    weights = np.array([current_values[ticker] / total_value for ticker in common_tickers])
    portfolio_returns = returns_df[common_tickers] @ weights

    try:
        benchmark_frame = await fetcher.get_price_history("SPY", "yahoo", days=365)
        benchmark_returns = log_returns(benchmark_frame["close"])
        aligned = pd.concat([portfolio_returns.rename("portfolio"), benchmark_returns.rename("benchmark")], axis=1).dropna()
    except Exception:
        aligned = pd.DataFrame()

    correlation_matrix = returns_df[common_tickers].corr().to_dict()
    var_95 = historical_var(portfolio_returns, 0.95) * total_value_inr
    var_99 = historical_var(portfolio_returns, 0.99) * total_value_inr
    cvar_95 = historical_cvar(portfolio_returns, 0.95) * total_value_inr
    cvar_99 = historical_cvar(portfolio_returns, 0.99) * total_value_inr

    ann_return = _annualised_arithmetic_return(portfolio_returns)
    ann_vol = _annualised_volatility(portfolio_returns)

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
        annualised_return=ann_return,
        annualised_volatility=ann_vol,
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

    price_results = await asyncio.gather(
        *[fetcher.get_price_history(ticker, asset_map[ticker]["data_source"], days=365) for ticker in tickers],
        return_exceptions=True,
    )
    price_data = {
        ticker: frame
        for ticker, frame in zip(tickers, price_results)
        if not isinstance(frame, Exception) and not frame.empty
    }
    usd_inr = await fetcher.get_usd_inr_rate()
    returns_df = await loop.run_in_executor(None, align_returns, price_data, asset_currencies, "USD", usd_inr)
    if returns_df.empty:
        raise AppError("Monte Carlo failed", "insufficient_returns", "Unable to compute portfolio returns", 400)

    common_tickers = [ticker for ticker in tickers if ticker in returns_df.columns]
    if not common_tickers:
        raise AppError("Monte Carlo failed", "insufficient_returns", "Unable to compute portfolio returns", 400)
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
    asset_classes = [asset_map[ticker]["asset_class"].value for ticker in common_tickers]

    # ── 1. Detect regime ──
    regime_state = 1  # default sideways
    if _regime_detector is not None and _regime_detector.is_fitted:
        try:
            market_proxy = returns_df.iloc[:, 0]
            regime_info = await loop.run_in_executor(None, _regime_detector.detect_regime, market_proxy)
            regime_state = regime_info.state
        except Exception:
            regime_state = 1

    # ── 2. Compute expected returns using the institutional engine ──
    cov_annual = await loop.run_in_executor(
        None, compute_covariance, returns_df[common_tickers], "ledoit_wolf", True, 252,
    )
    # Shrink volatility (smooth, not hard-capped)
    cov_annual_shrunk = await loop.run_in_executor(
        None, shrink_volatility, cov_annual, asset_classes, True, 252,
    )
    market_weights = compute_market_weights_from_volatility(cov_annual_shrunk)

    mu_daily, diagnostics = blend_expected_returns(
        cov_annual=cov_annual_shrunk,
        market_weights=market_weights,
        returns_df=returns_df[common_tickers],
        asset_classes=asset_classes,
        regime_state=regime_state,
    )

    # ── 3. Daily covariance for MC ──
    cov_daily = await loop.run_in_executor(
        None, compute_covariance, returns_df[common_tickers], "ledoit_wolf", False, 252,
    )
    cov_daily = await loop.run_in_executor(
        None, shrink_volatility, cov_daily, asset_classes, False, 252,
    )

    # ── 4. Run regime-switching Monte Carlo ──
    result = await loop.run_in_executor(
        None,
        simulate_portfolio,
        weights,
        mu_daily,
        cov_daily,
        total_value * usd_inr,
        n_paths or settings.MONTE_CARLO_PATHS,
        horizon_days or settings.MONTE_CARLO_HORIZON_DAYS,
        regime_state,    # regime_state
        True,            # use_student_t
        True,            # use_jumps
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


def _neutral_risk_metrics(portfolio_id: UUID, usd_inr: float) -> RiskMetrics:
    return RiskMetrics(
        portfolio_id=portfolio_id,
        usd_inr_rate=float(usd_inr),
        var_95=0.0,
        var_99=0.0,
        cvar_95=0.0,
        cvar_99=0.0,
        max_drawdown=0.0,
        sharpe_ratio=0.0,
        sortino_ratio=0.0,
        calmar_ratio=0.0,
        annualised_return=0.0,
        annualised_volatility=0.0,
        beta=0.0,
        correlation_matrix={},
    )
