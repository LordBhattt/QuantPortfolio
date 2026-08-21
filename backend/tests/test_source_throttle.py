import time

import pytest

pytest.importorskip("httpx")

from backend.quant.data_fetcher import _SourceThrottle


@pytest.mark.asyncio
async def test_throttle_spaces_out_calls_to_the_same_source() -> None:
    throttle = _SourceThrottle()
    start = time.monotonic()

    await throttle.wait("coingecko")
    await throttle.wait("coingecko")

    elapsed = time.monotonic() - start
    assert elapsed >= 2.0


@pytest.mark.asyncio
async def test_throttle_is_a_noop_without_a_source() -> None:
    throttle = _SourceThrottle()
    start = time.monotonic()

    await throttle.wait(None)
    await throttle.wait(None)

    elapsed = time.monotonic() - start
    assert elapsed < 0.5


@pytest.mark.asyncio
async def test_throttle_tracks_sources_independently() -> None:
    throttle = _SourceThrottle()
    await throttle.wait("coingecko")

    start = time.monotonic()
    await throttle.wait("yahoo")  # different source, much shorter min interval
    elapsed = time.monotonic() - start

    assert elapsed < 1.0
