"""Local historical price cache for the backtest engine.

Fetches each asset's full history once through the existing DataFetcher and
writes it to a local parquet file. Every later call only fetches the days
missing since the last update (a small request), not a full re-download, so
repeated backtest runs and dataset refreshes stay cheap on the free-tier
market data APIs. This cache is independent of the live request path used by
the Dashboard/Optimize/Risk/Analytics pages, which keep calling DataFetcher
directly with their own short-TTL Redis cache.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from backend.quant.data_fetcher import DataFetcher

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "historical"
DEFAULT_LOOKBACK_DAYS = 365 * 8
MIN_INCREMENTAL_LOOKBACK_DAYS = 30


def _cache_path(ticker: str) -> Path:
    safe_name = ticker.replace("/", "_").replace("=", "_")
    return DATA_DIR / f"{safe_name}.parquet"


def load_cached_prices(ticker: str) -> pd.DataFrame | None:
    path = _cache_path(ticker)
    if not path.exists():
        return None
    frame = pd.read_parquet(path)
    return frame if not frame.empty else None


async def update_cached_prices(
    fetcher: DataFetcher,
    ticker: str,
    source: str,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
) -> pd.DataFrame:
    """Return the up-to-date cached price history for `ticker`.

    First call for a ticker fetches `lookback_days` of history. Every
    subsequent call fetches only the days since the last cached date.
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    path = _cache_path(ticker)
    existing = load_cached_prices(ticker)

    if existing is None:
        frame = await fetcher.get_price_history(ticker, source, days=lookback_days)
        frame.to_parquet(path)
        return frame

    last_date = existing.index.max()
    days_stale = (pd.Timestamp.now().normalize() - last_date.normalize()).days
    if days_stale <= 0:
        return existing

    delta_days = min(max(days_stale + 5, MIN_INCREMENTAL_LOOKBACK_DAYS), lookback_days)
    fresh = await fetcher.get_price_history(ticker, source, days=delta_days)
    fresh = fresh[fresh.index > last_date]
    if fresh.empty:
        return existing

    combined = pd.concat([existing, fresh]).sort_index()
    combined = combined[~combined.index.duplicated(keep="last")]
    combined.to_parquet(path)
    return combined
