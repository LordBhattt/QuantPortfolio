"""
Optimization pipeline: institutional grade:
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
from typing import Any
from uuid import UUID

import numpy as np
import pandas as pd
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
    compute_equilibrium_returns,
    compute_market_weights_from_volatility,
)
from backend.quant.forecaster import ReturnForecaster
from backend.quant.mvo import constrained_mvo, efficient_frontier
from backend.quant.regime import RegimeDetector, RegimeState
from backend.quant.returns import align_returns
from backend.schemas.optimization import (
    AssetDiagnostics,
    AssetWeight,
    OptimizationDiagnostics,
    OptimizationRequest,
    OptimizationResult,
    PortfolioConstraints,
    RegimeProbabilities,
)
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


def get_ml_models() -> tuple[RegimeDetector | None, ReturnForecaster | None]:
    return _regime_detector, _return_forecaster


def optimize_from_returns(
    returns_df: pd.DataFrame,
    tickers: list[str],
    asset_classes: list[str],
    constraints: Any,
    risk_tolerance: float,
    use_regime: bool,
    regime_detector: Any,
    ml_forecasts: np.ndarray | None,
    use_ml: bool,
    user_views: list | None = None,
    risk_free_rate: float | None = None,
) -> dict:
    """
    Pure function: given aligned returns DataFrame, run the optimization pipeline.
    Returns dict with keys: weights (dict[str,float]), regime_state (int),
    expected_returns_annual (np.ndarray), cov_annual (np.ndarray).
    """
    rf = risk_free_rate if risk_free_rate is not None else settings.RISK_FREE_RATE

    # Resolve constraints
    resolved_constraints = constraints
    if isinstance(constraints, dict):
        resolved_constraints = PortfolioConstraints(**constraints)

    # 1. Detect regime
    regime_state = 1
    regime_probs = np.array([0.0, 1.0, 0.0])
    regime_info: RegimeState | None = None

    if use_regime and regime_detector is not None and getattr(regime_detector, "is_fitted", False):
        market_proxy = returns_df.iloc[:, 0]
        try:
            regime_info = regime_detector.detect_regime(market_proxy)
            regime_state = regime_info.state
            regime_probs = regime_info.probabilities
        except Exception:
            regime_state = 1
            regime_probs = np.array([0.0, 1.0, 0.0])

    # 2. Covariance with shrinkage + regime scaling
    cov = compute_covariance(returns_df, "ledoit_wolf", True, 252)
    cov = shrink_volatility(cov, asset_classes, True, 252)

    if regime_info is not None:
        cov = scale_covariance_by_regime(
            cov,
            regime_state,
            regime_info.cov_diag_scale,
            regime_info.cov_offdiag_scale,
        )

    # 3. Expected returns
    market_weights = compute_market_weights_from_volatility(cov)
    ml_forecasts_annual: np.ndarray | None = None
    if use_ml and ml_forecasts is not None:
        ml_forecasts_annual = ml_forecasts

    mu_daily, diagnostics = blend_expected_returns(
        cov_annual=cov,
        market_weights=market_weights,
        returns_df=returns_df,
        asset_classes=asset_classes,
        regime_state=regime_state,
        ml_forecasts=ml_forecasts_annual,
        base_risk_aversion=2.5,
    )
    mu_annual = mu_daily * 252

    # 4. User views via Black-Litterman
    optimization_cov = cov
    mu = mu_annual

    if user_views:
        user_view_rows: list[np.ndarray] = []
        user_view_returns: list[float] = []
        view_confidences: list[float] = []
        ticker_index = {ticker: index for index, ticker in enumerate(tickers)}

        for view in user_views:
            if view.ticker not in ticker_index:
                continue
            row = np.zeros(len(tickers))
            row[ticker_index[view.ticker]] = 1.0
            user_view_rows.append(row)
            user_view_returns.append(float(view.expected_return))
            view_confidences.append(float(view.confidence))

        if user_view_rows:
            P = np.array(user_view_rows)
            Q = np.array(user_view_returns)
            confidences = np.array(view_confidences)
            omega = build_omega_from_confidence(P=P, cov=cov, tau=0.025, confidences=confidences)
            risk_aversion = 2.5 * (regime_info.risk_aversion_mult if regime_info else 1.0)
            bl_inputs = BLInputs(
                cov=cov,
                market_weights=market_weights,
                risk_aversion=risk_aversion,
                tau=0.025,
                P=P,
                Q=Q,
                Omega=omega,
            )
            mu = black_litterman_returns(bl_inputs)
            posterior_delta = posterior_covariance(bl_inputs)
            optimization_cov = cov + posterior_delta

    # 5. Constrained MVO
    weight_map = constrained_mvo(
        mu,
        optimization_cov,
        tickers,
        asset_classes,
        resolved_constraints,
        risk_tolerance,
        rf,
    )

    return {
        "weights": weight_map,
        "regime_state": regime_state,
        "regime_probs": regime_probs,
        "regime_info": regime_info,
        "expected_returns_annual": mu,
        "cov_annual": cov,
        "optimization_cov": optimization_cov,
        "diagnostics": diagnostics,
    }


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
        # Fill None with equilibrium
        if any(v is not None for v in ml_list):
            raw_cov = compute_covariance(returns_df, "ledoit_wolf", True, 252)
            m_weights = compute_market_weights_from_volatility(raw_cov)
            eq_returns = compute_equilibrium_returns(raw_cov, m_weights, 2.5)
            ml_forecasts_annual = np.array([
                v if v is not None else float(eq_returns[i])
                for i, v in enumerate(ml_list)
            ])

    constraints = request.constraints or PortfolioConstraints(**portfolio["constraints"])

    # Call pure function optimize_from_returns in executor
    opt_result = await loop.run_in_executor(
        None,
        lambda: optimize_from_returns(
            returns_df=returns_df,
            tickers=tickers,
            asset_classes=asset_classes,
            constraints=constraints,
            risk_tolerance=request.risk_tolerance,
            use_regime=request.use_regime_scaling,
            regime_detector=_regime_detector,
            ml_forecasts=ml_forecasts_annual,
            use_ml=request.use_lstm_forecasts,
            user_views=request.user_views,
        ),
    )

    weight_map = opt_result["weights"]
    regime_state = opt_result["regime_state"]
    regime_probs = opt_result["regime_probs"]
    mu = opt_result["expected_returns_annual"]
    optimization_cov = opt_result["optimization_cov"]

    regime_label = _regime_detector.regime_label(regime_state) if _regime_detector else "sideways"

    frontier = await loop.run_in_executor(
        None, efficient_frontier, mu, optimization_cov, tickers, asset_classes,
        constraints, 50, settings.RISK_FREE_RATE,
    )

    # Compute current values + rebalancing
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

    # ── Build diagnostics ──
    diag_data = opt_result.get("diagnostics", {})
    tickers_list = opt_result.get("tickers", tickers)
    asset_classes_list = opt_result.get("asset_classes", asset_classes)
    eq_annual = diag_data.get("equilibrium_annual", [0.0] * len(tickers_list))
    hist_annual = diag_data.get("historical_annual", [0.0] * len(tickers_list))
    ml_annual = diag_data.get("ml_annual", [0.0] * len(tickers_list))
    mom_annual = diag_data.get("momentum_annual", [0.0] * len(tickers_list))
    blend_annual = diag_data.get("blended_annual", [0.0] * len(tickers_list))

    per_asset_diag = [
        AssetDiagnostics(
            ticker=t,
            asset_class=ac,
            equilibrium_return_annual=float(eq_annual[i]) if i < len(eq_annual) else 0.0,
            historical_return_annual=float(hist_annual[i]) if i < len(hist_annual) else 0.0,
            ml_return_annual=float(ml_annual[i]) if i < len(ml_annual) else 0.0,
            momentum_return_annual=float(mom_annual[i]) if i < len(mom_annual) else 0.0,
            blended_return_annual=float(blend_annual[i]) if i < len(blend_annual) else 0.0,
        )
        for i, (t, ac) in enumerate(zip(tickers_list, asset_classes_list))
    ]

    _probs = regime_probs if len(regime_probs) == 3 else np.array([0.0, 1.0, 0.0])
    regime_diag = RegimeProbabilities(
        bull=float(_probs[0]),
        sideways=float(_probs[1]),
        bear=float(_probs[2]),
        current_regime=regime_label,
    )

    model_kind = "none"
    ml_weight_used = 0.0
    use_ml_flag = getattr(request, "use_ml_forecast", None) or getattr(request, "use_lstm_forecasts", False)
    if _return_forecaster is not None and use_ml_flag:
        model_kind = getattr(_return_forecaster, "model_kind", "none")
        ml_weight_used = 0.30

    optimization_diagnostics = OptimizationDiagnostics(
        per_asset=per_asset_diag,
        regime_probabilities=regime_diag,
        model_kind=model_kind,
        ml_weight_used=ml_weight_used,
    )

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
        diagnostics=optimization_diagnostics,
    )
