from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.data_types import CurrentUser
from backend.database import get_db
from backend.dependencies import get_current_user
from backend.schemas.portfolio import HoldingCreate, HoldingOut, PortfolioCreate, PortfolioOut, PortfolioUpdate
from backend.services.portfolio_service import (
    add_holding,
    create_portfolio,
    delete_holding,
    delete_portfolio,
    get_portfolio,
    list_holdings,
    list_portfolios,
    update_portfolio,
)

router = APIRouter(prefix="/api/v1/portfolios", tags=["portfolios"])


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
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> HoldingOut:
    return await add_holding(payload, portfolio_id, current_user.id, db)


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
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    await delete_holding(portfolio_id, holding_id, current_user.id, db)
    return Response(status_code=204)
