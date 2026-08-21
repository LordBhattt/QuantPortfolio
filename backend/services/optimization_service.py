"""
Optimization pipeline — institutional grade:
1. Load portfolio holdings
2. Fetch price history + compute returns
3. Detect market regime (HMM + vol + trend)
4. Compute regime-aware expected returns (equilibrium + historical + ML + momentum)
5. Estimate covariance with volatility shrinkage
6. Blend views with Black-Litterman
7. Run constrained MVO
"""

import asyncio
import logging
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
from backend.quant.covariance import compute_covariance, scale_covariance_by_regime, shrink_volatility
from backend.quant.data_fetcher import DataFetcher
from backend.quant.expected_returns import (
    blend_expected_returns,
    compute_market_weights_from_volatility,
)
from backend.quant.forecaster import ReturnForecaster
from backend.quant.mvo import constrained_mvo, efficient_frontier
from backend.quant.regime import RegimeDetector, RegimeState
from backend.quant.returns import align_returns
from backend.schemas.optimization import AssetWeight, OptimizationRequest, OptimizationResult, PortfolioConstraints
from backend.services.portfolio_service import load_portfolio_snapshot
from backend.services.risk_service import set_regime_detector

settings = get_settings()
logger = logging.getLogger(__name__)

_regime_detector: RegimeDetector | None = None
_return_forecaster: ReturnForecaster | None = None


def init_ml_models(regime_detector: RegimeDetector, return_forecaster: ReturnForecaster) -> None:
    global _regime_detector, _return_forecaster
    _regime_detector = regime_detector
    _return_forecaster = return_forecaster
    # Share regime detector with risk service
    set_regime_detector(regime_detector)


def get_regime_detector() -> RegimeDetector | None:
    """Expose the live-fitted regime detector so other modules (e.g. the
    backtest engine) can replay the exact same model instead of fitting a
    separate one."""
    return _regime_detector


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

    price_results = await asyncio.gather(
        *[
            fetcher.get_price_history(
                ticker=ticker,
                source=asset_map[ticker]["data_source"],
                days=settings.MVO_ROLLING_WINDOW_DAYS + 30,
            )
            for ticker in tickers
        ],
        return_exceptions=True,
    )
    price_data = {
        ticker: frame
        for ticker, frame in zip(tickers, price_results)
        if not isinstance(frame, Exception) and not frame.empty
    }
    tickers = [ticker for ticker in tickers if ticker in price_data]
    if not tickers:
        raise AppError("Optimization failed", "market_data_unavailable", "Market data is temporarily unavailable", 503)
    quantities = {ticker: quantities[ticker] for ticker in tickers}
    asset_currencies = {ticker: asset_currencies[ticker] for ticker in tickers}
    asset_classes = [asset_map[ticker]["asset_class"].value for ticker in tickers]
    usd_inr = await fetcher.get_usd_inr_rate()

    returns_df = await loop.run_in_executor(
        None, align_returns, price_data, asset_currencies, "USD", usd_inr,
    )
    returns_df = returns_df.tail(settings.MVO_ROLLING_WINDOW_DAYS)
    if returns_df.empty or len(returns_df.columns) == 0:
        raise AppError("Optimization failed", "insufficient_returns", "Unable to build aligned return matrix", 400)

    # ── 1. Detect regime ──
    regime_state = 1
    regime_probs = np.array([0.0, 1.0, 0.0])
    regime_info: RegimeState | None = None

    if request.use_regime_scaling and _regime_detector is not None and _regime_detector.is_fitted:
        market_proxy = returns_df.iloc[:, 0]
        try:
            regime_info = await loop.run_in_executor(None, _regime_detector.detect_regime, market_proxy)
            regime_state = regime_info.state
            regime_probs = regime_info.probabilities
        except Exception:
            regime_state = 1
            regime_probs = np.array([0.0, 1.0, 0.0])

    regime_label = _regime_detector.regime_label(regime_state) if _regime_detector else "sideways"

    # ── 2. Covariance with shrinkage + regime scaling ──
    cov = await loop.run_in_executor(None, compute_covariance, returns_df, "ledoit_wolf", True, 252)
    cov = await loop.run_in_executor(None, shrink_volatility, cov, asset_classes, True, 252)

    if regime_info is not None:
        cov = await loop.run_in_executor(
            None, scale_covariance_by_regime, cov, regime_state,
            regime_info.cov_diag_scale, regime_info.cov_offdiag_scale,
        )

    # ── 3. Compute expected returns via institutional engine ──
    market_weights = compute_market_weights_from_volatility(cov)

    # Gather ML forecasts if available
    ml_forecasts_annual: np.ndarray | None = None
    if request.use_lstm_forecasts and _return_forecaster is not None and _return_forecaster.model is not None:
        ml_list = []
        for ticker in tickers:
            asset_class = asset_map[ticker]["asset_class"].value
            try:
                pred = await loop.run_in_executor(
                    None, _return_forecaster.predict_blended, price_data[ticker], asset_class, 0.30,
                )
                ml_list.append(float(pred))
            except Exception:
                ml_list.append(None)
        # Fill None with equilibrium (will be handled by blend_expected_returns)
        if any(v is not None for v in ml_list):
            from backend.quant.expected_returns import compute_equilibrium_returns
            risk_aversion = 2.5 * (regime_info.risk_aversion_mult if regime_info else 1.0)
            eq_returns = compute_equilibrium_returns(cov, market_weights, risk_aversion)
            ml_forecasts_annual = np.array([
                v if v is not None else float(eq_returns[i])
                for i, v in enumerate(ml_list)
            ])

    mu_daily, diagnostics = blend_expected_returns(
        cov_annual=cov,
        market_weights=market_weights,
        returns_df=returns_df,
        asset_classes=asset_classes,
        regime_state=regime_state,
        ml_forecasts=ml_forecasts_annual,
        base_risk_aversion=2.5,
    )

    # Convert daily mu to annual for BL/MVO (they expect annualised)
    mu_annual = mu_daily * 252

    # ── 4. User views via Black-Litterman ──
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

    P = np.array(user_view_rows) if user_view_rows else None
    Q = np.array(user_view_returns) if user_view_returns else None
    confidences = np.array(view_confidences) if view_confidences else None
    omega = (
        build_omega_from_confidence(P=P, cov=cov, tau=0.025, confidences=confidences)
        if P is not None and confidences is not None
        else None
    )

    if P is not None:
        # Use BL to blend user views with our expected returns
        bl_inputs = BLInputs(
            cov=cov,
            market_weights=market_weights,
            risk_aversion=2.5 * (regime_info.risk_aversion_mult if regime_info else 1.0),
            tau=0.025,
            P=P, Q=Q, Omega=omega,
        )
        mu = await loop.run_in_executor(None, black_litterman_returns, bl_inputs)
        posterior_delta = await loop.run_in_executor(None, posterior_covariance, bl_inputs)
        optimization_cov = cov + posterior_delta
    else:
        mu = mu_annual
        optimization_cov = cov

    # ── 5. MVO ──
    constraints = request.constraints or PortfolioConstraints(**portfolio["constraints"])
    weight_map = await loop.run_in_executor(
        None, constrained_mvo, mu, optimization_cov, tickers, asset_classes,
        constraints, request.risk_tolerance, settings.RISK_FREE_RATE,
    )
    frontier = await loop.run_in_executor(
        None, efficient_frontier, mu, optimization_cov, tickers, asset_classes,
        constraints, 50, settings.RISK_FREE_RATE,
    )

    # ── 6. Compute current values + rebalancing ──
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
    current_values: dict[str, float] = {}
    for ticker in tickers:
        live_price_inr = live_prices_inr.get(ticker)
        if live_price_inr is not None:
            current_values[ticker] = float(live_price_inr * quantities[ticker] / usd_inr)
            continue
        current_price = float(price_data[ticker]["close"].iloc[-1])
        current_values[ticker] = (
            current_price * quantities[ticker]
            * (1.0 / usd_inr if asset_currencies[ticker].upper() == "INR" else 1.0)
        )
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
