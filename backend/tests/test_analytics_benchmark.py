from __future__ import annotations

import pandas as pd
import pytest

pytest.importorskip("pandas")

from backend.services.analytics_service import _build_benchmark_series


class FakeFetcher:
    def __init__(self) -> None:
        dates = pd.date_range("2024-01-01", periods=5, freq="B")
        self.frames = {
            "^NSEI": pd.DataFrame({"close": [20000, 20100, 20250, 20400, 20600]}, index=dates),
            "SPY": pd.DataFrame({"close": [400, 405, 408, 412, 416]}, index=dates),
        }

    async def get_price_history(self, ticker: str, source: str, days: int = 365):
        del source, days
        return self.frames[ticker]


@pytest.mark.asyncio
async def test_build_benchmark_series_returns_normalized_comparison() -> None:
    portfolio_series = pd.Series([100.0, 103.0, 104.0, 106.0, 109.0], index=pd.date_range("2024-01-01", periods=5, freq="B"))

    result = await _build_benchmark_series(portfolio_series, FakeFetcher())

    assert len(result) == 5
    assert result[0].portfolio == 0.0
    assert result[0].nifty50 == 0.0
    assert result[0].sp500 == 0.0
    assert result[-1].portfolio > result[-1].nifty50
    assert result[-1].sp500 > 0.0