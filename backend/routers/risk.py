from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from backend.data_types import CurrentUser
from backend.database import get_db
from backend.dependencies import get_current_user, get_fetcher
from backend.quant.data_fetcher import DataFetcher
from backend.schemas.risk import MonteCarloResult, RiskMetrics
from backend.schemas.stress import CustomShockRequest, StressTestResponse
from backend.services.risk_service import compute_risk_metrics, run_monte_carlo
from backend.services.stress_service import run_custom_stress, run_stress_test

router = APIRouter(prefix="/api/v1/risk", tags=["risk"])


@router.get("/regime/history")
async def get_regime_history(
    days: int = Query(default=252, ge=30, le=1260),
    fetcher: DataFetcher = Depends(get_fetcher),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[dict]:
    """Return SPY close price with HMM regime label for the last N trading days."""
    import numpy as np
    from backend.services.optimization_service import get_ml_models

    regime_detector, _ = get_ml_models()

    # Fetch SPY history
    spy_df = await fetcher.get_price_history("SPY", source="yahoo", days=days + 60)
    if spy_df is None or spy_df.empty:
        return []

    spy_df = spy_df.sort_index().tail(days + 60)
    closes = spy_df["close"].dropna()
    if len(closes) < 2:
        return []

    import pandas as pd
    log_returns = closes.pct_change().dropna()

    result = []
    for i in range(min(days, len(closes))):
        idx = len(closes) - days + i
        if idx < 2:
            continue
        date_val = closes.index[idx]
        close_val = float(closes.iloc[idx])

        regime_label = "sideways"
        regime_int = 1
        if regime_detector is not None and regime_detector.is_fitted:
            window = log_returns.iloc[max(0, idx - 60):idx]
            if len(window) >= 10:
                try:
                    state = regime_detector.detect_regime(window)
                    regime_label = state.label
                    regime_int = state.state
                except Exception:
                    pass

        result.append({
            "date": date_val.strftime("%Y-%m-%d") if hasattr(date_val, "strftime") else str(date_val),
            "close": close_val,
            "regime": regime_label,
            "regime_int": regime_int,
        })

    return result


@router.get("/{portfolio_id}", response_model=RiskMetrics)
async def get_risk_metrics(
    portfolio_id: UUID,
    db: AsyncSession = Depends(get_db),
    fetcher: DataFetcher = Depends(get_fetcher),
    current_user: CurrentUser = Depends(get_current_user),
) -> RiskMetrics:
    return await compute_risk_metrics(portfolio_id, current_user.id, db, fetcher)


@router.get("/{portfolio_id}/monte-carlo", response_model=MonteCarloResult)
async def get_monte_carlo(
    portfolio_id: UUID,
    n_paths: int = Query(default=1000, ge=100, le=10000),
    horizon_days: int = Query(default=252, ge=30, le=1260),
    db: AsyncSession = Depends(get_db),
    fetcher: DataFetcher = Depends(get_fetcher),
    current_user: CurrentUser = Depends(get_current_user),
) -> MonteCarloResult:
    return await run_monte_carlo(
        portfolio_id=portfolio_id,
        user_id=current_user.id,
        db=db,
        fetcher=fetcher,
        n_paths=n_paths,
        horizon_days=horizon_days,
    )


@router.get("/{portfolio_id}/stress", response_model=StressTestResponse)
async def get_stress_test(
    portfolio_id: UUID,
    db: AsyncSession = Depends(get_db),
    fetcher: DataFetcher = Depends(get_fetcher),
    current_user: CurrentUser = Depends(get_current_user),
) -> StressTestResponse:
    return await run_stress_test(
        portfolio_id=portfolio_id,
        user_id=current_user.id,
        db=db,
        fetcher=fetcher,
    )


@router.post("/{portfolio_id}/stress/custom")
async def custom_stress_test(
    portfolio_id: UUID,
    shock: CustomShockRequest,
    db: AsyncSession = Depends(get_db),
    fetcher: DataFetcher = Depends(get_fetcher),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    return await run_custom_stress(
        portfolio_id=portfolio_id,
        user_id=current_user.id,
        db=db,
        fetcher=fetcher,
        shock=shock,
    )
