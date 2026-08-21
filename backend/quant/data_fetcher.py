"""
Single entry point for all external market data calls.
Methods return raw DataFrames or primitive payloads without business logic.
"""

import asyncio
import contextlib
import io
import time
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

YAHOO_CRYPTO_TICKER_MAP = {
    "BTC": "BTC-USD",
    "ETH": "ETH-USD",
    "SOL": "SOL-USD",
    "DOGE": "DOGE-USD",
    "MATIC": "MATIC-USD",
}

# Minimum seconds between two outbound requests to the same provider. Defense
# in depth on top of the existing Redis cache: keeps normal live usage (and
# any burst of concurrent requests, e.g. a portfolio with many holdings) from
# outrunning free-tier limits, most importantly CoinGecko's ~10-30 req/min.
_MIN_INTERVAL_SECONDS: dict[str, float] = {
    "yahoo": 0.3,
    "coingecko": 2.0,
    "amfi": 0.3,
    "nse": 1.0,
    "fx": 0.3,
}


class _SourceThrottle:
    """Serializes and spaces out requests per data-provider `source` name."""

    def __init__(self) -> None:
        self._last_call_at: dict[str, float] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def _lock_for(self, source: str) -> asyncio.Lock:
        lock = self._locks.get(source)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[source] = lock
        return lock

    async def wait(self, source: str | None) -> None:
        if not source:
            return
        min_interval = _MIN_INTERVAL_SECONDS.get(source, 0.0)
        if min_interval <= 0:
            return
        async with self._lock_for(source):
            elapsed = time.monotonic() - self._last_call_at.get(source, 0.0)
            remaining = min_interval - elapsed
            if remaining > 0:
                await asyncio.sleep(remaining)
            self._last_call_at[source] = time.monotonic()


class DataFetcher:
    def __init__(self, cache: RedisCache) -> None:
        self.cache = cache
        self.client = httpx.AsyncClient(timeout=30.0, headers=self._browser_headers())
        self._throttle = _SourceThrottle()

    @staticmethod
    def _browser_headers() -> dict[str, str]:
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://www.nseindia.com/",
        }

    async def close(self) -> None:
        await self.client.aclose()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _get_json(
        self, url: str, params: dict | None = None, headers: dict[str, str] | None = None, source: str | None = None
    ) -> dict:
        await self._throttle.wait(source)
        response = await self.client.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response.json()

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def _get_text(
        self, url: str, params: dict | None = None, headers: dict[str, str] | None = None, source: str | None = None
    ) -> str:
        await self._throttle.wait(source)
        response = await self.client.get(url, params=params, headers=headers)
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
            try:
                frame = await self._fetch_coingecko(ticker, days)
            except Exception:
                frame = await self._fetch_yahoo_crypto_fallback(ticker, days)
        elif source_name == "amfi":
            frame = await self._fetch_amfi_nav(ticker, days)
        else:
            raise ValueError(f"Unknown source: {source}")

        await self.cache.set(cache_key, frame.to_json(date_format="iso"), ttl=settings.PRICE_HISTORY_TTL_SECONDS)
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
        data = await self._get_json(url, params=params, source="yahoo")
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

    async def _fetch_yahoo_crypto_fallback(self, ticker: str, days: int) -> pd.DataFrame:
        yahoo_ticker = YAHOO_CRYPTO_TICKER_MAP.get(ticker.upper(), f"{ticker.upper()}-USD")
        return await self._fetch_yahoo(yahoo_ticker, days)

    async def _fetch_coingecko(self, ticker: str, days: int) -> pd.DataFrame:
        coin_id = COINGECKO_ID_MAP.get(ticker.upper(), ticker.lower())
        url = f"{settings.COINGECKO_BASE}/coins/{coin_id}/market_chart"
        params = {"vs_currency": "usd", "days": days, "interval": "daily"}
        data = await self._get_json(url, params=params, source="coingecko")
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
        data = await self._get_json(url, source="amfi")
        records = list(reversed(data["data"][:days]))
        frame = pd.DataFrame(records)
        frame["date"] = pd.to_datetime(frame["date"], format="%d-%m-%Y")
        frame["close"] = frame["nav"].astype(float)
        frame["open"] = frame["close"]
        frame["high"] = frame["close"]
        frame["low"] = frame["close"]
        frame["volume"] = 0.0
        return frame[["date", "open", "high", "low", "close", "volume"]].set_index("date").sort_index()

    async def _fetch_nse_last_price(self, ticker: str) -> float | None:
        symbol = ticker.upper().replace(".NS", "")
        cache_key = f"nse:last_price:{symbol}"
        cached = await self.cache.get(cache_key)
        if cached is not None:
            with contextlib.suppress(ValueError):
                return float(cached)

        url = f"https://www.nseindia.com/api/quote-equity?symbol={symbol}"
        try:
            data = await self._get_json(url, headers=self._browser_headers(), source="nse")
            price = float(data["priceInfo"]["lastPrice"])
        except Exception:
            return None

        await self.cache.set(cache_key, str(price), ttl=settings.LIVE_QUOTE_TTL_SECONDS)
        return price

    async def _fetch_yahoo_quote_prices(self, tickers: list[str]) -> dict[str, float]:
        if not tickers:
            return {}

        quote_base = settings.YAHOO_BASE.replace("/v8/finance", "/v7/finance")
        url = f"{quote_base}/quote"
        prices: dict[str, float] = {}
        for start in range(0, len(tickers), 50):
            chunk = tickers[start : start + 50]
            data = await self._get_json(url, params={"symbols": ",".join(chunk)}, source="yahoo")
            results = data.get("quoteResponse", {}).get("result", [])
            for item in results:
                symbol = str(item.get("symbol", "")).upper()
                price = item.get("regularMarketPrice")
                if price is None:
                    price = item.get("postMarketPrice") or item.get("preMarketPrice")
                try:
                    parsed = float(price)
                except (TypeError, ValueError):
                    continue
                if parsed > 0:
                    prices[symbol] = parsed
        return prices

    async def _fetch_usd_inr_rate(self) -> float:
        try:
            frame = await self._fetch_yahoo("INR=X", days=5)
            return float(frame["close"].iloc[-1])
        except Exception:
            pass

        url = "https://open.er-api.com/v6/latest/USD"
        data = await self._get_json(url, headers=self._browser_headers(), source="fx")
        return float(data["rates"]["INR"])

    async def get_usd_inr_rate(self) -> float:
        cache_key = "fx:usd_inr"
        cached = await self.cache.get(cache_key)
        if cached:
            return float(cached)
        rate = await self._fetch_usd_inr_rate()
        await self.cache.set(cache_key, str(rate), ttl=3600)
        return rate

    async def get_latest_price_in_inr(
        self,
        ticker: str,
        source: str,
        exchange: str | None = None,
        currency: str | None = None,
    ) -> float | None:
        normalized_source = source.lower()
        normalized_exchange = (exchange or "").upper()
        normalized_currency = (currency or "INR").upper()

        if normalized_source == "coingecko":
            frame = await self.get_price_history(ticker, source, days=5)
            if frame.empty:
                return None
            price = float(frame["close"].iloc[-1])
            if normalized_currency == "USD":
                price *= await self.get_usd_inr_rate()
            return price

        if normalized_exchange == "NSE" or ticker.upper().endswith(".NS"):
            quote = await self._fetch_nse_last_price(ticker)
            if quote is not None:
                return quote

        if normalized_source == "amfi":
            frame = await self.get_price_history(ticker, source, days=5)
            if frame.empty:
                return None
            return float(frame["close"].iloc[-1])

        try:
            frame = await self.get_price_history(ticker, source, days=5)
        except Exception:
            return None

        if frame.empty:
            return None

        price = float(frame["close"].iloc[-1])
        if normalized_currency == "USD":
            try:
                price *= await self.get_usd_inr_rate()
            except Exception:
                return None
        return price

    async def get_latest_prices_in_inr(self, instruments: list[dict]) -> dict[str, float]:
        """
        Return fresh INR quotes for multiple holdings while keeping external calls bounded.

        Yahoo symbols are fetched through one batched quote request per 50 tickers, then
        cached per instrument. Slower/history-backed sources still use their existing
        per-source cache paths.
        """
        if not instruments:
            return {}

        prices: dict[str, float] = {}
        pending_yahoo: list[dict] = []
        pending_other: list[dict] = []

        for item in instruments:
            ticker = str(item["ticker"]).upper()
            source = str(item.get("source") or item.get("data_source") or "yahoo").lower()
            exchange = str(item.get("exchange") or "").upper()
            currency = str(item.get("currency") or "INR").upper()
            cache_key = f"quote_inr:{source}:{ticker}:{exchange}:{currency}"
            cached = await self.cache.get(cache_key)
            if cached is not None:
                with contextlib.suppress(ValueError):
                    prices[ticker] = float(cached)
                    continue

            normalized = {
                "ticker": ticker,
                "source": source,
                "exchange": exchange,
                "currency": currency,
                "cache_key": cache_key,
            }
            if source == "yahoo":
                pending_yahoo.append(normalized)
            else:
                pending_other.append(normalized)

        usd_inr_rate: float | None = None
        if any(item["currency"] == "USD" for item in pending_yahoo):
            with contextlib.suppress(Exception):
                usd_inr_rate = await self.get_usd_inr_rate()

        if pending_yahoo:
            try:
                yahoo_prices = await self._fetch_yahoo_quote_prices([item["ticker"] for item in pending_yahoo])
            except Exception:
                yahoo_prices = {}

            for item in pending_yahoo:
                ticker = item["ticker"]
                native_price = yahoo_prices.get(ticker)
                if native_price is None and (item["exchange"] == "NSE" or ticker.endswith(".NS")):
                    native_price = await self._fetch_nse_last_price(ticker)
                if native_price is None:
                    fallback = await self.get_latest_price_in_inr(
                        ticker,
                        item["source"],
                        item["exchange"],
                        item["currency"],
                    )
                    if fallback is not None:
                        prices[ticker] = fallback
                    continue

                if item["currency"] == "USD" and usd_inr_rate is None:
                    continue
                price_inr = native_price * (usd_inr_rate if item["currency"] == "USD" else 1.0)
                prices[ticker] = float(price_inr)
                await self.cache.set(item["cache_key"], str(float(price_inr)), ttl=settings.LIVE_QUOTE_TTL_SECONDS)

        if pending_other:
            tasks = [
                self.get_latest_price_in_inr(item["ticker"], item["source"], item["exchange"], item["currency"])
                for item in pending_other
            ]
            resolved = await asyncio.gather(*tasks, return_exceptions=True)
            for item, value in zip(pending_other, resolved):
                if isinstance(value, Exception) or value is None:
                    continue
                prices[item["ticker"]] = float(value)
                await self.cache.set(item["cache_key"], str(float(value)), ttl=settings.LIVE_QUOTE_TTL_SECONDS)

        return prices

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
