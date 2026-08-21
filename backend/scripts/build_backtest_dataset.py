"""Build/refresh the local historical dataset used by the backtest engine.

Safe to re-run: the first run fetches full history per asset, every run
after that only fetches the days missing since the last run (see
backend/quant/backtest_data.py). Does not touch the live request path used
by the rest of the app.

Usage:
    python -m backend.scripts.build_backtest_dataset
"""

import asyncio
from pathlib import Path
import sys

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from backend.cache.redis_cache import RedisCache
from backend.quant.backtest_data import update_cached_prices
from backend.quant.backtest_universe import BACKTEST_UNIVERSE
from backend.quant.data_fetcher import DataFetcher


async def main() -> None:
    cache = RedisCache()
    await cache.connect()
    fetcher = DataFetcher(cache)
    try:
        for asset in BACKTEST_UNIVERSE:
            ticker, source = asset.ticker, asset.source
            try:
                frame = await update_cached_prices(fetcher, ticker, source)
                print(f"{ticker:15s} ({source:9s}) -> {len(frame):5d} rows, through {frame.index.max().date()}")
            except Exception as exc:
                print(f"{ticker:15s} ({source:9s}) -> FAILED: {exc}")
    finally:
        await fetcher.close()
        await cache.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
