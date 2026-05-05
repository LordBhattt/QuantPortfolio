from __future__ import annotations

from unittest.mock import AsyncMock

import pandas as pd
import pytest

pytest.importorskip("httpx")
pytest.importorskip("pandas")

from backend.quant.data_fetcher import DataFetcher


class DummyCache:
    def __init__(self) -> None:
        self.storage: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self.storage.get(key)

    async def set(self, key: str, value: str, ttl: int | None = None) -> None:
        del ttl
        self.storage[key] = value


@pytest.mark.asyncio
async def test_get_price_history_mocks_yahoo_response_and_uses_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    fetcher = DataFetcher(DummyCache())
    payload = {
        "chart": {
            "result": [
                {
                    "timestamp": [1704067200, 1704153600],
                    "indicators": {
                        "quote": [
                            {
                                "open": [100.0, 101.0],
                                "high": [101.0, 102.0],
                                "low": [99.0, 100.0],
                                "close": [100.5, 101.5],
                                "volume": [1000, 1200],
                            }
                        ],
                        "adjclose": [{"adjclose": [100.5, 101.5]}],
                    },
                }
            ]
        }
    }
    mocked_get_json = AsyncMock(return_value=payload)
    monkeypatch.setattr(fetcher, "_get_json", mocked_get_json)

    first_frame = await fetcher.get_price_history("SPY", "yahoo", days=2)
    second_frame = await fetcher.get_price_history("SPY", "yahoo", days=2)

    assert mocked_get_json.await_count == 1
    assert list(first_frame["close"]) == [100.5, 101.5]
    assert list(second_frame["close"]) == [100.5, 101.5]
    await fetcher.close()


@pytest.mark.asyncio
async def test_get_price_history_mocks_coingecko_response(monkeypatch: pytest.MonkeyPatch) -> None:
    fetcher = DataFetcher(DummyCache())
    payload = {
        "prices": [[1704067200000, 1.0], [1704153600000, 1.1]],
        "total_volumes": [[1704067200000, 10.0], [1704153600000, 11.0]],
    }
    mocked_get_json = AsyncMock(return_value=payload)
    monkeypatch.setattr(fetcher, "_get_json", mocked_get_json)

    frame = await fetcher.get_price_history("BTC", "coingecko", days=2)

    assert mocked_get_json.await_count == 1
    assert list(frame["close"]) == [1.0, 1.1]
    assert list(frame["volume"]) == [10.0, 11.0]
    await fetcher.close()