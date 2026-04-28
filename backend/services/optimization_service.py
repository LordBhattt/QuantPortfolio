"""
Optimization pipeline:
1. Load portfolio holdings
2. Fetch price history
3. Compute returns and covariance
4. Detect regime
5. Blend views with Black-Litterman
6. Run constrained MVO
"""

import asyncio
from uuid import UUID

import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.errors import AppError
from backend.quant.black_litterman import (
    BLInputs,
    black_litterman_returns,
    build_omega_from_confidence,
    posterior_covariance,
)
from backend.quant.covariance import compute_covariance, scale_covariance_by_regime
from backend.quant.data_fetcher import DataFetcher
from backend.quant.forecaster import ReturnForecaster
from backend.quant.mvo import constrained_mvo, efficient_frontier
from backend.quant.regime import RegimeDetector
from backend.quant.returns import align_returns
from backend.schemas.optimization import AssetWeight, OptimizationRequest, OptimizationResult, PortfolioConstraints
from backend.services.portfolio_service import load_portfolio_snapshot

settings = get_settings()

_regime_detector: RegimeDetector | None = None
_return_forecaster: ReturnForecaster | None = None


def init_ml_models(regime_detector: RegimeDetector, return_forecaster: ReturnForecaster) -> None:
    global _regime_detector, _return_forecaster
    _regime_detector = regime_detector
    _return_forecaster = return_forecaster


async def run_optimization(
    request: OptimizationRequest,
    user_id: UUID,
    db: AsyncSession,
    fetcher: DataFetcher,
) -> OptimizationResult:
    loop = asyncio.get_running_loop()
    portfolio, holdings, assets = await load_portfolio_snapshot(request.portfolio_id, user_id, db)
    if not holdings:
        raise AppError("Optimization failed", "empty_portfolio", "Portfolio has no holdings", 400)

    asset_map = {row["ticker"]: row for row in assets}
    missing_assets = [row["ticker"] for row in holdings if row["ticker"] not in asset_map]
    if missing_assets:
        raise AppError(
            "Optimization failed",
            "missing_asset_metadata",
            f"Missing asset metadata for: {', '.join(missing_assets)}",
            400,
        )

    tickers = [row["ticker"] for row in holdings]
    quantities = {row["ticker"]: float(row["quantity"]) for row in holdings}
    asset_currencies = {ticker: asset_map[ticker]["currency"] for ticker in tickers}
    asset_classes = [asset_map[ticker]["asset_class"].value for ticker in tickers]

    price_frames = await asyncio.gather(
        *[
            fetcher.get_price_history(
                ticker=ticker,
                source=asset_map[ticker]["data_source"],
                days=settings.MVO_ROLLING_WINDOW_DAYS + 30,
            )
            for ticker in tickers
        ]
    )
    price_data = dict(zip(tickers, price_frames))
    usd_inr = await fetcher.get_usd_inr_rate()

    returns_df = await loop.run_in_executor(
        None,
        align_returns,
        price_data,
        asset_currencies,
        "USD",
        usd_inr,
    )
    returns_df = returns_df.tail(settings.MVO_ROLLING_WINDOW_DAYS)
    if returns_df.empty or len(returns_df.columns) == 0:
        raise AppError("Optimization failed", "insufficient_returns", "Unable to build aligned return matrix", 400)

    cov = await loop.run_in_executor(None, compute_covariance, returns_df, "ledoit_wolf", True, 252)

    regime_state = 1
    regime_probs = np.array([0.0, 1.0, 0.0])
    if request.use_regime_scaling and _regime_detector is not None and _regime_detector.is_fitted:
        market_proxy = returns_df.iloc[:, 0]
        try:
            regime_state, regime_probs = await loop.run_in_executor(None, _regime_detector.predict, market_proxy)
            cov = await loop.run_in_executor(None, scale_covariance_by_regime, cov, regime_state, 3)
        except Exception:
            regime_state = 1
            regime_probs = np.array([0.0, 1.0, 0.0])

    regime_label = _regime_detector.regime_label(regime_state) if _regime_detector else "sideways"

    user_view_rows: list[np.ndarray] = []
    user_view_returns: list[float] = []
    view_confidences: list[float] = []
    ticker_index = {ticker: index for index, ticker in enumerate(tickers)}

    for view in request.user_views:
        if view.ticker not in ticker_index:
            continue
        row = np.zeros(len(tickers))
        row[ticker_index[view.ticker]] = 1.0
        user_view_rows.append(row)
        user_view_returns.append(float(view.expected_return))
        view_confidences.append(float(view.confidence))

    if request.use_lstm_forecasts and _return_forecaster is not None and _return_forecaster.model is not None:
        for index, ticker in enumerate(tickers):
            try:
                expected_return = await loop.run_in_executor(None, _return_forecaster.predict, price_data[ticker])
            except Exception:
                continue
            row = np.zeros(len(tickers))
            row[index] = 1.0
            user_view_rows.append(row)
            user_view_returns.append(float(expected_return))
            view_confidences.append(0.4)

    P = np.array(user_view_rows) if user_view_rows else None
    Q = np.array(user_view_returns) if user_view_returns else None
    confidences = np.array(view_confidences) if view_confidences else None
    omega = (
        build_omega_from_confidence(P=P, cov=cov, tau=0.025, confidences=confidences)
        if P is not None and confidences is not None
        else None
    )

    market_weights = np.ones(len(tickers)) / len(tickers)
    bl_inputs = BLInputs(
        cov=cov,
        market_weights=market_weights,
        risk_aversion=2.5,
        tau=0.025,
        P=P,
        Q=Q,
        Omega=omega,
    )
    mu = await loop.run_in_executor(None, black_litterman_returns, bl_inputs)
    posterior_delta = await loop.run_in_executor(None, posterior_covariance, bl_inputs)
    optimization_cov = cov + posterior_delta if P is not None else cov

    constraints = request.constraints or PortfolioConstraints(**portfolio["constraints"])
    weight_map = await loop.run_in_executor(
        None,
        constrained_mvo,
        mu,
        optimization_cov,
        tickers,
        asset_classes,
        constraints,
        request.risk_tolerance,
        settings.RISK_FREE_RATE,
    )
    frontier = await loop.run_in_executor(
        None,
        efficient_frontier,
        mu,
        optimization_cov,
        tickers,
        asset_classes,
        constraints,
        50,
        settings.RISK_FREE_RATE,
    )

    current_prices = {ticker: float(price_data[ticker]["close"].iloc[-1]) for ticker in tickers}
    current_values = {
        ticker: current_prices[ticker]
        * quantities[ticker]
        * (1.0 / usd_inr if asset_currencies[ticker].upper() == "INR" else 1.0)
        for ticker in tickers
    }
    total_value = float(sum(current_values.values()))
    if total_value <= 0:
        raise AppError("Optimization failed", "invalid_portfolio_value", "Portfolio current value must be positive", 400)

    weight_vector = np.array([weight_map[ticker] for ticker in tickers])
    portfolio_return = float(mu @ weight_vector)
    portfolio_volatility = float(np.sqrt(weight_vector @ optimization_cov @ weight_vector))
    sharpe = (
        (portfolio_return - settings.RISK_FREE_RATE) / portfolio_volatility
        if portfolio_volatility > 0
        else 0.0
    )

    optimal_weights: list[AssetWeight] = []
    rebalance_trades: list[AssetWeight] = []
    for ticker in tickers:
        target_value = weight_map[ticker] * total_value
        current_value = current_values[ticker]
        delta = target_value - current_value
        item = AssetWeight(
            ticker=ticker,
            asset_class=asset_map[ticker]["asset_class"].value,
            weight=float(weight_map[ticker]),
            current_value_usd=float(current_value),
            target_value_usd=float(target_value),
            trade_delta_usd=float(delta),
        )
        optimal_weights.append(item)
        if abs(delta) / total_value > 0.01:
            rebalance_trades.append(item)

    return OptimizationResult(
        portfolio_id=request.portfolio_id,
        regime=regime_label,
        regime_probability=float(regime_probs[regime_state]),
        usd_inr_rate=float(usd_inr),
        optimal_weights=optimal_weights,
        portfolio_return=portfolio_return,
        portfolio_volatility=portfolio_volatility,
        sharpe_ratio=sharpe,
        efficient_frontier=frontier,
        rebalance_trades=rebalance_trades,
    )
