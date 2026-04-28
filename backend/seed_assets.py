"""
Run once: python seed_assets.py
Seeds the assets table with Indian and US instruments across all asset classes.
Safe to re-run -- skips existing tickers.
"""

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

load_dotenv(Path(__file__).resolve().parent / ".env")

from backend.models.asset import AssetClass, assets

DATABASE_URL = os.environ["DATABASE_URL"]

ASSETS = [
    {"ticker": "RELIANCE.NS", "name": "Reliance Industries", "asset_class": AssetClass.STOCK, "exchange": "NSE", "currency": "INR", "data_source": "yahoo", "is_active": True},
    {"ticker": "TCS.NS", "name": "Tata Consultancy Services", "asset_class": AssetClass.STOCK, "exchange": "NSE", "currency": "INR", "data_source": "yahoo", "is_active": True},
    {"ticker": "INFY.NS", "name": "Infosys", "asset_class": AssetClass.STOCK, "exchange": "NSE", "currency": "INR", "data_source": "yahoo", "is_active": True},
    {"ticker": "HDFCBANK.NS", "name": "HDFC Bank", "asset_class": AssetClass.STOCK, "exchange": "NSE", "currency": "INR", "data_source": "yahoo", "is_active": True},
    {"ticker": "ICICIBANK.NS", "name": "ICICI Bank", "asset_class": AssetClass.STOCK, "exchange": "NSE", "currency": "INR", "data_source": "yahoo", "is_active": True},
    {"ticker": "WIPRO.NS", "name": "Wipro", "asset_class": AssetClass.STOCK, "exchange": "NSE", "currency": "INR", "data_source": "yahoo", "is_active": True},
    {"ticker": "BAJFINANCE.NS", "name": "Bajaj Finance", "asset_class": AssetClass.STOCK, "exchange": "NSE", "currency": "INR", "data_source": "yahoo", "is_active": True},
    {"ticker": "TATAMOTORS.NS", "name": "Tata Motors", "asset_class": AssetClass.STOCK, "exchange": "NSE", "currency": "INR", "data_source": "yahoo", "is_active": True},
    {"ticker": "SBIN.NS", "name": "State Bank of India", "asset_class": AssetClass.STOCK, "exchange": "NSE", "currency": "INR", "data_source": "yahoo", "is_active": True},
    {"ticker": "ADANIENT.NS", "name": "Adani Enterprises", "asset_class": AssetClass.STOCK, "exchange": "NSE", "currency": "INR", "data_source": "yahoo", "is_active": True},
    {"ticker": "MARUTI.NS", "name": "Maruti Suzuki", "asset_class": AssetClass.STOCK, "exchange": "NSE", "currency": "INR", "data_source": "yahoo", "is_active": True},
    {"ticker": "ASIANPAINT.NS", "name": "Asian Paints", "asset_class": AssetClass.STOCK, "exchange": "NSE", "currency": "INR", "data_source": "yahoo", "is_active": True},
    {"ticker": "TITAN.NS", "name": "Titan Company", "asset_class": AssetClass.STOCK, "exchange": "NSE", "currency": "INR", "data_source": "yahoo", "is_active": True},
    {"ticker": "SUNPHARMA.NS", "name": "Sun Pharmaceutical", "asset_class": AssetClass.STOCK, "exchange": "NSE", "currency": "INR", "data_source": "yahoo", "is_active": True},
    {"ticker": "ULTRACEMCO.NS", "name": "UltraTech Cement", "asset_class": AssetClass.STOCK, "exchange": "NSE", "currency": "INR", "data_source": "yahoo", "is_active": True},
    {"ticker": "AAPL", "name": "Apple Inc.", "asset_class": AssetClass.STOCK, "exchange": "NASDAQ", "currency": "USD", "data_source": "yahoo", "is_active": True},
    {"ticker": "MSFT", "name": "Microsoft", "asset_class": AssetClass.STOCK, "exchange": "NASDAQ", "currency": "USD", "data_source": "yahoo", "is_active": True},
    {"ticker": "GOOGL", "name": "Alphabet", "asset_class": AssetClass.STOCK, "exchange": "NASDAQ", "currency": "USD", "data_source": "yahoo", "is_active": True},
    {"ticker": "AMZN", "name": "Amazon", "asset_class": AssetClass.STOCK, "exchange": "NASDAQ", "currency": "USD", "data_source": "yahoo", "is_active": True},
    {"ticker": "NVDA", "name": "NVIDIA", "asset_class": AssetClass.STOCK, "exchange": "NASDAQ", "currency": "USD", "data_source": "yahoo", "is_active": True},
    {"ticker": "META", "name": "Meta Platforms", "asset_class": AssetClass.STOCK, "exchange": "NASDAQ", "currency": "USD", "data_source": "yahoo", "is_active": True},
    {"ticker": "TSLA", "name": "Tesla", "asset_class": AssetClass.STOCK, "exchange": "NASDAQ", "currency": "USD", "data_source": "yahoo", "is_active": True},
    {"ticker": "BRK-B", "name": "Berkshire Hathaway B", "asset_class": AssetClass.STOCK, "exchange": "NYSE", "currency": "USD", "data_source": "yahoo", "is_active": True},
    {"ticker": "bitcoin", "name": "Bitcoin", "asset_class": AssetClass.CRYPTO, "exchange": "CRYPTO", "currency": "USD", "data_source": "coingecko", "is_active": True},
    {"ticker": "ethereum", "name": "Ethereum", "asset_class": AssetClass.CRYPTO, "exchange": "CRYPTO", "currency": "USD", "data_source": "coingecko", "is_active": True},
    {"ticker": "solana", "name": "Solana", "asset_class": AssetClass.CRYPTO, "exchange": "CRYPTO", "currency": "USD", "data_source": "coingecko", "is_active": True},
    {"ticker": "ripple", "name": "XRP", "asset_class": AssetClass.CRYPTO, "exchange": "CRYPTO", "currency": "USD", "data_source": "coingecko", "is_active": True},
    {"ticker": "cardano", "name": "Cardano", "asset_class": AssetClass.CRYPTO, "exchange": "CRYPTO", "currency": "USD", "data_source": "coingecko", "is_active": True},
    {"ticker": "polkadot", "name": "Polkadot", "asset_class": AssetClass.CRYPTO, "exchange": "CRYPTO", "currency": "USD", "data_source": "coingecko", "is_active": True},
    {"ticker": "GLD", "name": "SPDR Gold ETF", "asset_class": AssetClass.GOLD, "exchange": "NYSE", "currency": "USD", "data_source": "yahoo", "is_active": True},
    {"ticker": "SGOL", "name": "Aberdeen Gold ETF", "asset_class": AssetClass.GOLD, "exchange": "NYSE", "currency": "USD", "data_source": "yahoo", "is_active": True},
    {"ticker": "IAU", "name": "iShares Gold Trust", "asset_class": AssetClass.GOLD, "exchange": "NYSE", "currency": "USD", "data_source": "yahoo", "is_active": True},
    {"ticker": "GLDM", "name": "SPDR Gold MiniShares", "asset_class": AssetClass.GOLD, "exchange": "NYSE", "currency": "USD", "data_source": "yahoo", "is_active": True},
    {"ticker": "NIFTYBEES.NS", "name": "Nippon Nifty BeES", "asset_class": AssetClass.MF_ETF, "exchange": "NSE", "currency": "INR", "data_source": "yahoo", "is_active": True},
    {"ticker": "JUNIORBEES.NS", "name": "Nippon Junior BeES", "asset_class": AssetClass.MF_ETF, "exchange": "NSE", "currency": "INR", "data_source": "yahoo", "is_active": True},
    {"ticker": "GOLDBEES.NS", "name": "Nippon Gold BeES", "asset_class": AssetClass.MF_ETF, "exchange": "NSE", "currency": "INR", "data_source": "yahoo", "is_active": True},
    {"ticker": "BANKBEES.NS", "name": "Nippon Bank BeES", "asset_class": AssetClass.MF_ETF, "exchange": "NSE", "currency": "INR", "data_source": "yahoo", "is_active": True},
    {"ticker": "SPY", "name": "SPDR S&P 500 ETF", "asset_class": AssetClass.MF_ETF, "exchange": "NYSE", "currency": "USD", "data_source": "yahoo", "is_active": True},
    {"ticker": "QQQ", "name": "Invesco QQQ Nasdaq ETF", "asset_class": AssetClass.MF_ETF, "exchange": "NASDAQ", "currency": "USD", "data_source": "yahoo", "is_active": True},
    {"ticker": "VTI", "name": "Vanguard Total Market ETF", "asset_class": AssetClass.MF_ETF, "exchange": "NYSE", "currency": "USD", "data_source": "yahoo", "is_active": True},
    {"ticker": "VEA", "name": "Vanguard Developed Markets", "asset_class": AssetClass.MF_ETF, "exchange": "NYSE", "currency": "USD", "data_source": "yahoo", "is_active": True},
    {"ticker": "VWO", "name": "Vanguard Emerging Markets", "asset_class": AssetClass.MF_ETF, "exchange": "NYSE", "currency": "USD", "data_source": "yahoo", "is_active": True},
    {"ticker": "ARKK", "name": "ARK Innovation ETF", "asset_class": AssetClass.MF_ETF, "exchange": "NYSE", "currency": "USD", "data_source": "yahoo", "is_active": True},
    {"ticker": "TLT", "name": "iShares 20Y Treasury ETF", "asset_class": AssetClass.BOND, "exchange": "NASDAQ", "currency": "USD", "data_source": "yahoo", "is_active": True},
    {"ticker": "BND", "name": "Vanguard Total Bond ETF", "asset_class": AssetClass.BOND, "exchange": "NASDAQ", "currency": "USD", "data_source": "yahoo", "is_active": True},
    {"ticker": "AGG", "name": "iShares Core US Aggregate", "asset_class": AssetClass.BOND, "exchange": "NYSE", "currency": "USD", "data_source": "yahoo", "is_active": True},
    {"ticker": "IEF", "name": "iShares 7-10Y Treasury ETF", "asset_class": AssetClass.BOND, "exchange": "NASDAQ", "currency": "USD", "data_source": "yahoo", "is_active": True},
    {"ticker": "GSEC.NS", "name": "Bharat Bond ETF Apr 2032", "asset_class": AssetClass.BOND, "exchange": "NSE", "currency": "INR", "data_source": "yahoo", "is_active": True},
]


async def seed() -> None:
    engine = create_async_engine(DATABASE_URL)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    async with session_factory() as session:
        added = 0
        skipped = 0
        for asset_data in ASSETS:
            existing = await session.execute(
                select(assets.c.ticker).where(assets.c.ticker == asset_data["ticker"])
            )
            if existing.scalar_one_or_none() is not None:
                skipped += 1
                continue
            await session.execute(assets.insert().values(**asset_data))
            added += 1
        await session.commit()
        print(f"Done. Added: {added} | Already existed: {skipped} | Total: {len(ASSETS)}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
