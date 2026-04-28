from sqlalchemy import delete, insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.errors import AppError
from backend.models.asset import AssetClass, assets
from backend.schemas.asset import AssetCreate, AssetOut, AssetUpdate

DEFAULT_ASSETS: list[dict] = [
    {
        "ticker": "RELIANCE.NS",
        "name": "Reliance Industries",
        "asset_class": AssetClass.STOCK,
        "exchange": "NSE",
        "currency": "INR",
        "data_source": "yahoo",
        "is_active": True,
    },
    {
        "ticker": "TCS.NS",
        "name": "Tata Consultancy Services",
        "asset_class": AssetClass.STOCK,
        "exchange": "NSE",
        "currency": "INR",
        "data_source": "yahoo",
        "is_active": True,
    },
    {
        "ticker": "AAPL",
        "name": "Apple Inc.",
        "asset_class": AssetClass.STOCK,
        "exchange": "NASDAQ",
        "currency": "USD",
        "data_source": "yahoo",
        "is_active": True,
    },
    {
        "ticker": "MSFT",
        "name": "Microsoft Corporation",
        "asset_class": AssetClass.STOCK,
        "exchange": "NASDAQ",
        "currency": "USD",
        "data_source": "yahoo",
        "is_active": True,
    },
    {
        "ticker": "BTC",
        "name": "Bitcoin",
        "asset_class": AssetClass.CRYPTO,
        "exchange": "CRYPTO",
        "currency": "USD",
        "data_source": "coingecko",
        "is_active": True,
    },
    {
        "ticker": "ETH",
        "name": "Ethereum",
        "asset_class": AssetClass.CRYPTO,
        "exchange": "CRYPTO",
        "currency": "USD",
        "data_source": "coingecko",
        "is_active": True,
    },
    {
        "ticker": "GLD",
        "name": "SPDR Gold Shares",
        "asset_class": AssetClass.GOLD,
        "exchange": "NYSEARCA",
        "currency": "USD",
        "data_source": "yahoo",
        "is_active": True,
    },
    {
        "ticker": "GOLDBEES.NS",
        "name": "Nippon India ETF Gold BeES",
        "asset_class": AssetClass.GOLD,
        "exchange": "NSE",
        "currency": "INR",
        "data_source": "yahoo",
        "is_active": True,
    },
    {
        "ticker": "NIFTYBEES.NS",
        "name": "Nippon India ETF Nifty BeES",
        "asset_class": AssetClass.MF_ETF,
        "exchange": "NSE",
        "currency": "INR",
        "data_source": "yahoo",
        "is_active": True,
    },
    {
        "ticker": "SPY",
        "name": "SPDR S&P 500 ETF Trust",
        "asset_class": AssetClass.MF_ETF,
        "exchange": "NYSEARCA",
        "currency": "USD",
        "data_source": "yahoo",
        "is_active": True,
    },
    {
        "ticker": "LIQUIDBEES.NS",
        "name": "Nippon India ETF Liquid BeES",
        "asset_class": AssetClass.BOND,
        "exchange": "NSE",
        "currency": "INR",
        "data_source": "yahoo",
        "is_active": True,
    },
    {
        "ticker": "TLT",
        "name": "iShares 20+ Year Treasury Bond ETF",
        "asset_class": AssetClass.BOND,
        "exchange": "NASDAQ",
        "currency": "USD",
        "data_source": "yahoo",
        "is_active": True,
    },
]


async def create_asset(payload: AssetCreate, db: AsyncSession) -> AssetOut:
    existing = await db.execute(select(assets.c.ticker).where(assets.c.ticker == payload.ticker))
    if existing.scalar_one_or_none() is not None:
        raise AppError("Asset creation failed", "asset_exists", f"Asset {payload.ticker} already exists", 400)

    statement = insert(assets).values(**payload.model_dump()).returning(assets)
    result = await db.execute(statement)
    return AssetOut.model_validate(result.mappings().one())


async def seed_default_assets(db: AsyncSession) -> None:
    existing = set((await db.execute(select(assets.c.ticker))).scalars().all())
    missing = [asset for asset in DEFAULT_ASSETS if asset["ticker"] not in existing]
    if missing:
        await db.execute(insert(assets), missing)


async def list_assets(
    db: AsyncSession,
    q: str | None = None,
    asset_class: str | None = None,
    active_only: bool = True,
) -> list[AssetOut]:
    statement = select(assets)
    if q:
        pattern = f"%{q.strip()}%"
        statement = statement.where(or_(assets.c.ticker.ilike(pattern), assets.c.name.ilike(pattern)))
    if asset_class:
        try:
            normalized_class = AssetClass(asset_class.lower())
        except ValueError as exc:
            raise AppError(
                "Asset query failed",
                "invalid_asset_class",
                f"Unsupported asset class: {asset_class}",
                400,
            ) from exc
        statement = statement.where(assets.c.asset_class == normalized_class)
    if active_only:
        statement = statement.where(assets.c.is_active.is_(True))
    statement = statement.order_by(assets.c.ticker.asc())

    result = await db.execute(statement)
    return [AssetOut.model_validate(row) for row in result.mappings().all()]


async def get_asset(ticker: str, db: AsyncSession) -> AssetOut:
    result = await db.execute(select(assets).where(assets.c.ticker == ticker.upper()))
    row = result.mappings().first()
    if row is None:
        raise AppError("Asset not found", "asset_not_found", f"Asset {ticker} not found", 404)
    return AssetOut.model_validate(row)


async def update_asset(ticker: str, payload: AssetUpdate, db: AsyncSession) -> AssetOut:
    await get_asset(ticker, db)
    values = payload.model_dump(exclude_none=True)
    if not values:
        return await get_asset(ticker, db)
    statement = update(assets).where(assets.c.ticker == ticker.upper()).values(**values).returning(assets)
    result = await db.execute(statement)
    row = result.mappings().one_or_none()
    if row is None:
        raise AppError("Asset update failed", "asset_not_found", f"Asset {ticker} not found", 404)
    return AssetOut.model_validate(row)


async def delete_asset(ticker: str, db: AsyncSession) -> None:
    result = await db.execute(delete(assets).where(assets.c.ticker == ticker.upper()).returning(assets.c.ticker))
    if result.scalar_one_or_none() is None:
        raise AppError("Asset delete failed", "asset_not_found", f"Asset {ticker} not found", 404)
