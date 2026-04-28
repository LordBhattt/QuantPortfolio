"""
Single entry point for all external market data calls.
Methods return raw DataFrames or primitive payloads without business logic.
"""

import asyncio
import io
import zipfile
from datetime import datetime, timedelta, timezone
from urllib.request import urlopen

import httpx
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential

from backend.cache.redis_cache import RedisCache
from backend.config import get_settings

settings = get_settings()

COINGECKO_ID_MAP = {
    "BTC": "bitcoin",
    "ETH": "ethereum",
    "SOL": "solana",
    "DOGE": "dogecoin",
    "MATIC": "matic-network",
}


class DataFetcher:
    def __init__(self, cache: RedisCache) -> None:
        self.cache = cache
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self) -> None:
        await self.client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _get_json(self, url: str, params: dict | None = None) -> dict:
        response = await self.client.get(url, params=params)
        response.raise_for_status()
        return response.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _get_text(self, url: str, params: dict | None = None) -> str:
        response = await self.client.get(url, params=params)
        response.raise_for_status()
        return response.text

    async def get_price_history(self, ticker: str, source: str, days: int = 365) -> pd.DataFrame:
        cache_key = f"prices:{source}:{ticker}:{days}"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return pd.read_json(io.StringIO(cached))

        source_name = source.lower()
        if source_name == "yahoo":
            frame = await self._fetch_yahoo(ticker, days)
        elif source_name == "coingecko":
            frame = await self._fetch_coingecko(ticker, days)
        elif source_name == "amfi":
            frame = await self._fetch_amfi_nav(ticker, days)
        else:
            raise ValueError(f"Unknown source: {source}")

        await self.cache.set(cache_key, frame.to_json(date_format="iso"), ttl=3600)
        return frame

    async def _fetch_yahoo(self, ticker: str, days: int) -> pd.DataFrame:
        now = datetime.now(timezone.utc)
        end = int(now.timestamp())
        start = int((now - timedelta(days=days)).timestamp())
        url = f"{settings.YAHOO_BASE}/chart/{ticker}"
        params = {
            "period1": start,
            "period2": end,
            "interval": "1d",
            "events": "history",
            "includeAdjustedClose": "true",
        }
        data = await self._get_json(url, params=params)
        result = data["chart"]["result"][0]
        quote = result["indicators"]["quote"][0]
        timestamps = result["timestamp"]
        adjusted = result["indicators"].get("adjclose", [{}])[0].get("adjclose", quote.get("close", []))
        frame = pd.DataFrame(
            {
                "date": pd.to_datetime(timestamps, unit="s", utc=True).tz_localize(None).normalize(),
                "open": quote.get("open"),
                "high": quote.get("high"),
                "low": quote.get("low"),
                "close": adjusted,
                "volume": quote.get("volume"),
            }
        )
        frame = frame.dropna(subset=["close"]).set_index("date").sort_index()
        frame["open"] = frame["open"].fillna(frame["close"])
        frame["high"] = frame["high"].fillna(frame["close"])
        frame["low"] = frame["low"].fillna(frame["close"])
        frame["volume"] = frame["volume"].fillna(0.0)
        return frame.astype(float)

    async def _fetch_coingecko(self, ticker: str, days: int) -> pd.DataFrame:
        coin_id = COINGECKO_ID_MAP.get(ticker.upper(), ticker.lower())
        url = f"{settings.COINGECKO_BASE}/coins/{coin_id}/market_chart"
        params = {"vs_currency": "usd", "days": days, "interval": "daily"}
        data = await self._get_json(url, params=params)
        prices = data["prices"]
        volumes = {item[0]: item[1] for item in data.get("total_volumes", [])}
        frame = pd.DataFrame(prices, columns=["ts", "close"])
        frame["date"] = pd.to_datetime(frame["ts"], unit="ms").dt.normalize()
        frame["volume"] = frame["ts"].map(volumes).fillna(0.0)
        frame["open"] = frame["close"]
        frame["high"] = frame["close"]
        frame["low"] = frame["close"]
        return frame.drop(columns=["ts"]).set_index("date").sort_index().astype(float)

    async def _fetch_amfi_nav(self, ticker: str, days: int) -> pd.DataFrame:
        url = f"https://api.mfapi.in/mf/{ticker}"
        data = await self._get_json(url)
        records = list(reversed(data["data"][:days]))
        frame = pd.DataFrame(records)
        frame["date"] = pd.to_datetime(frame["date"], format="%d-%m-%Y")
        frame["close"] = frame["nav"].astype(float)
        frame["open"] = frame["close"]
        frame["high"] = frame["close"]
        frame["low"] = frame["close"]
        frame["volume"] = 0.0
        return frame[["date", "open", "high", "low", "close", "volume"]].set_index("date").sort_index()

    async def get_usd_inr_rate(self) -> float:
        cache_key = "fx:usd_inr"
        cached = await self.cache.get(cache_key)
        if cached:
            return float(cached)
        frame = await self._fetch_yahoo("INR=X", days=5)
        rate = float(frame["close"].iloc[-1])
        await self.cache.set(cache_key, str(rate), ttl=3600)
        return rate

    async def get_fama_french_factors(self) -> pd.DataFrame:
        cache_key = "ff5:factors"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            return pd.read_json(io.StringIO(cached))

        url = (
            "https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/ftp/"
            "F-F_Research_Data_5_Factors_2x3_daily_CSV.zip"
        )
        loop = asyncio.get_running_loop()
        frame = await loop.run_in_executor(None, self._parse_ff5, url)
        await self.cache.set(cache_key, frame.to_json(date_format="iso"), ttl=86400)
        return frame

    def _parse_ff5(self, url: str) -> pd.DataFrame:
        with urlopen(url, timeout=30) as response:
            payload = response.read()
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            filename = next(name for name in archive.namelist() if name.lower().endswith(".csv"))
            with archive.open(filename) as handle:
                content = handle.read().decode("utf-8", errors="ignore")

        lines = content.splitlines()
        start = next(index for index, line in enumerate(lines) if line.strip().startswith("19"))
        data_lines = []
        for line in lines[start:]:
            stripped = line.strip()
            if not stripped:
                break
            head = stripped.split(",")[0]
            if not head.isdigit() or len(head) != 8:
                break
            data_lines.append(stripped)

        frame = pd.read_csv(
            io.StringIO("\n".join(data_lines)),
            names=["date", "Mkt-RF", "SMB", "HML", "RMW", "CMA", "RF"],
        )
        frame["date"] = pd.to_datetime(frame["date"].astype(str), format="%Y%m%d")
        frame = frame.set_index("date")
        frame = frame.apply(pd.to_numeric, errors="coerce").dropna() / 100.0
        return frame
