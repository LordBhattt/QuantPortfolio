from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.data_types import CurrentUser
from backend.database import get_db
from backend.dependencies import get_current_user
from backend.schemas.asset import AssetCreate, AssetOut, AssetUpdate
from backend.services.asset_service import create_asset, delete_asset, get_asset, list_assets, update_asset

router = APIRouter(prefix="/api/v1/assets", tags=["assets"])


@router.get("/", response_model=list[AssetOut])
async def list_assets_endpoint(
    q: str | None = Query(default=None),
    asset_class: str | None = Query(default=None, alias="class"),
    active_only: bool = Query(default=True),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[AssetOut]:
    del current_user
    return await list_assets(db=db, q=q, asset_class=asset_class, active_only=active_only)


@router.post("/", response_model=AssetOut, status_code=201)
async def create_asset_endpoint(
    payload: AssetCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AssetOut:
    del current_user
    return await create_asset(payload, db)


@router.get("/{ticker}", response_model=AssetOut)
async def get_asset_endpoint(
    ticker: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AssetOut:
    del current_user
    return await get_asset(ticker, db)


@router.patch("/{ticker}", response_model=AssetOut)
async def update_asset_endpoint(
    ticker: str,
    payload: AssetUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> AssetOut:
    del current_user
    return await update_asset(ticker, payload, db)


@router.delete("/{ticker}", status_code=204)
async def delete_asset_endpoint(
    ticker: str,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    del current_user
    await delete_asset(ticker, db)
    return Response(status_code=204)
