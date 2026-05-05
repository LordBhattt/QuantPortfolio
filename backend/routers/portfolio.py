import asyncio
from collections import defaultdict
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Response
from sqlalchemy import insert, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.data_types import CurrentUser
from backend.database import AsyncSessionLocal, get_db
from backend.dependencies import get_current_user, get_fetcher
from backend.errors import AppError
from backend.models.portfolio import portfolios
from backend.models.portfolio_alert import portfolio_alerts
from backend.schemas.portfolio import HoldingCreate, HoldingOut, PortfolioCreate, PortfolioOut, PortfolioUpdate
from backend.schemas.optimization import OptimizationRequest
from backend.services.optimization_service import run_optimization
from backend.services.portfolio_service import (
    add_holding,
    add_holdings,
    create_portfolio,
    delete_holding,
    delete_portfolio,
    get_portfolio,
    list_holdings,
    list_portfolios,
    update_portfolio,
)

router = APIRouter(prefix="/api/v1/portfolios", tags=["portfolios"])

_REOPTIMIZATION_DELAY_SECONDS = 2
_DRIFT_ALERT_THRESHOLD = 0.05


@router.post("/", response_model=PortfolioOut, status_code=201)
async def create_portfolio_endpoint(
    payload: PortfolioCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioOut:
    return await create_portfolio(payload, current_user.id, db)


@router.get("/", response_model=list[PortfolioOut])
async def list_portfolios_endpoint(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[PortfolioOut]:
    return await list_portfolios(current_user.id, db)


@router.get("/{portfolio_id}", response_model=PortfolioOut)
async def get_portfolio_endpoint(
    portfolio_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioOut:
    return await get_portfolio(portfolio_id, current_user.id, db)


@router.patch("/{portfolio_id}", response_model=PortfolioOut)
async def update_portfolio_endpoint(
    portfolio_id: UUID,
    payload: PortfolioUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> PortfolioOut:
    return await update_portfolio(payload, portfolio_id, current_user.id, db)


@router.delete("/{portfolio_id}", status_code=204)
async def delete_portfolio_endpoint(
    portfolio_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    await delete_portfolio(portfolio_id, current_user.id, db)
    return Response(status_code=204)


@router.post("/{portfolio_id}/holdings", response_model=HoldingOut, status_code=201)
async def add_holding_endpoint(
    portfolio_id: UUID,
    payload: HoldingCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> HoldingOut:
    holding = await add_holding(payload, portfolio_id, current_user.id, db)
    background_tasks.add_task(_reoptimize_portfolio_after_change, portfolio_id, current_user.id)
    return holding


@router.post("/{portfolio_id}/holdings/bulk", response_model=list[HoldingOut], status_code=201)
async def add_holdings_endpoint(
    portfolio_id: UUID,
    payload: list[HoldingCreate],
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[HoldingOut]:
    holdings_created = await add_holdings(payload, portfolio_id, current_user.id, db)
    background_tasks.add_task(_reoptimize_portfolio_after_change, portfolio_id, current_user.id)
    return holdings_created


@router.get("/{portfolio_id}/holdings", response_model=list[HoldingOut])
async def list_holdings_endpoint(
    portfolio_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[HoldingOut]:
    return await list_holdings(portfolio_id, current_user.id, db)


@router.delete("/{portfolio_id}/holdings/{holding_id}", status_code=204)
async def delete_holding_endpoint(
    portfolio_id: UUID,
    holding_id: UUID,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    await delete_holding(portfolio_id, holding_id, current_user.id, db)
    background_tasks.add_task(_reoptimize_portfolio_after_change, portfolio_id, current_user.id)
    return Response(status_code=204)


async def _reoptimize_portfolio_after_change(portfolio_id: UUID, user_id: UUID) -> None:
    await asyncio.sleep(_REOPTIMIZATION_DELAY_SECONDS)
    try:
        fetcher = get_fetcher()
    except AppError:
        return

    request = OptimizationRequest(
        portfolio_id=portfolio_id,
        risk_tolerance=0.5,
        use_regime_scaling=True,
        use_lstm_forecasts=False,
    )

    async with AsyncSessionLocal() as task_db:
        try:
            result = await run_optimization(request, user_id, task_db, fetcher)
        except AppError as exc:
            if exc.code == "empty_portfolio":
                await task_db.execute(
                    update(portfolios)
                    .where(portfolios.c.id == portfolio_id, portfolios.c.user_id == user_id)
                    .values(last_optimized_weights={})
                )
                await task_db.commit()
            else:
                await task_db.rollback()
            return

        recommended_weights = _aggregate_asset_class_weights(result.optimal_weights, "weight")
        actual_weights = _aggregate_asset_class_weights(result.optimal_weights, "current_value_usd")

        await task_db.execute(
            update(portfolios)
            .where(portfolios.c.id == portfolio_id, portfolios.c.user_id == user_id)
            .values(last_optimized_weights=recommended_weights)
        )

        if _has_significant_drift(recommended_weights, actual_weights):
            await task_db.execute(
                insert(portfolio_alerts).values(
                    portfolio_id=portfolio_id,
                    alert_type="post_addition_drift",
                    message="Your new holding has shifted your portfolio allocation. Consider rebalancing.",
                    is_read=False,
                )
            )

        await task_db.commit()


def _aggregate_asset_class_weights(weight_rows: list, value_field: str) -> dict[str, float]:
    class_values: dict[str, float] = defaultdict(float)
    total = 0.0
    for row in weight_rows:
        class_values[getattr(row, "asset_class")] += float(getattr(row, value_field))
        total += float(getattr(row, value_field))

    if total <= 0:
        return {}
    return {asset_class: value / total for asset_class, value in class_values.items()}


def _has_significant_drift(recommended_weights: dict[str, float], actual_weights: dict[str, float]) -> bool:
    asset_classes = set(recommended_weights) | set(actual_weights)
    for asset_class in asset_classes:
        if abs(float(recommended_weights.get(asset_class, 0.0)) - float(actual_weights.get(asset_class, 0.0))) > _DRIFT_ALERT_THRESHOLD:
            return True
    return False
