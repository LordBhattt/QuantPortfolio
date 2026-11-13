"""Stress test service - orchestrates historical scenario and custom shock tests."""

import asyncio
import logging
from pathlib import Path
from uuid import UUID

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from backend.errors import AppError
from backend.quant.data_fetcher import DataFetcher
from backend.quant.stress import (
    HISTORICAL_SCENARIOS,
    PROXY_MAP,
    compute_custom_shock,
    compute_historical_scenario,
)
from backend.schemas.stress import (
    CustomShockRequest,
    HoldingImpactOut,
    ScenarioResultOut,
    StressTestResponse,
)
from backend.services.portfolio_service import load_portfolio_snapshot

logger = logging.getLogger(__name__)

# Days needed for recent scenarios (COVID 2020, Rate Hike 2022): ~5 years is enough
_RECENT_HISTORY_DAYS = 1825  # 5 years
# Days needed to cover GFC (2008-2009): ~18 years
_GFC_HISTORY_DAYS = 6500

# Scenarios that require long history (pre-2018)
_LONG_HISTORY_SCENARIOS = {"GFC"}

# Proxy tickers always needed for scenario proxying
_PROXY_TICKERS = list(set(PROXY_MAP.values()))  # SPY, BTC-USD, GLD, AGG


def _load_from_parquet_cache(ticker: str) -> pd.DataFrame | None:
    """Try to load price data from local parquet cache files."""
    cache_dir = Path("backend/data/cache")
    if not cache_dir.exists():
        return None
    stem = ticker.replace(".", "_")
    matches = sorted(cache_dir.glob(f"{stem}_*.parquet"))
    if not matches:
        return None
    try:
        df = pd.read_parquet(matches[-1])
        df.columns = [c.lower() for c in df.columns]
        df.index = pd.to_datetime(df.index)
        if df.index.tz is not None:
            df.index = df.index.tz_localize(None)
        return df.sort_index()
    except Exception as exc:
        logger.warning("Failed to load parquet cache for %s: %s", ticker, exc)
        return None


async def run_stress_test(
    portfolio_id: UUID,
    user_id: UUID,
    db: AsyncSession,
    fetcher: DataFetcher,
) -> StressTestResponse:
    _, holdings, assets = await load_portfolio_snapshot(portfolio_id, user_id, db)
    if not holdings:
        raise AppError("Stress test failed", "empty_portfolio", "Portfolio has no holdings", 400)

    asset_map = {row["ticker"]: row for row in assets}
    tickers = [row["ticker"] for row in holdings if row["ticker"] in asset_map]
    quantities = {row["ticker"]: float(row["quantity"]) for row in holdings}
    asset_currencies = {ticker: asset_map[ticker]["currency"] for ticker in tickers}

    # Strategy: load price data efficiently.
    # 1. Try local parquet cache first (fast, covers 2018-now for recent scenarios).
    # 2. For tickers not in cache, fetch ~5 years from network (covers COVID and 2022).
    # 3. For GFC scenario (2008-2009), ALL holdings fall back to proxies (pre-2018).
    #    Fetch only the long-lived proxy tickers (SPY, GLD, AGG) with long history.
    price_data: dict[str, pd.DataFrame] = {}

    # Step 1: load from parquet cache (portfolio holdings + recent proxies)
    all_tickers_needed = list(set(tickers + _PROXY_TICKERS))
    for t in all_tickers_needed:
        cached_df = _load_from_parquet_cache(t)
        if cached_df is not None and not cached_df.empty:
            price_data[t] = cached_df

    # Step 2: fetch missing tickers from network (5 years, covers COVID + 2022)
    missing_recent = [t for t in all_tickers_needed if t not in price_data]
    if missing_recent:
        recent_results = await asyncio.gather(
            *[fetcher.get_price_history(t, "yahoo", days=_RECENT_HISTORY_DAYS) for t in missing_recent],
            return_exceptions=True,
        )
        for t, frame in zip(missing_recent, recent_results):
            if not isinstance(frame, Exception) and frame is not None and not frame.empty:
                price_data[t] = frame

    # Step 3: for GFC scenario, fetch SPY and GLD with long history (pre-2018).
    # BTC-USD did not exist in 2008 so skip it.
    gfc_scenario = next((s for s in HISTORICAL_SCENARIOS if s["name"] == "GFC"), None)
    if gfc_scenario:
        gfc_start = pd.Timestamp(gfc_scenario["start"])
        long_proxies = [t for t in _PROXY_TICKERS if t not in ("BTC-USD",)]
        long_fetch_needed = [
            t for t in long_proxies
            if t not in price_data or price_data[t].index.min() > gfc_start
        ]
        if long_fetch_needed:
            long_results = await asyncio.gather(
                *[fetcher.get_price_history(t, "yahoo", days=_GFC_HISTORY_DAYS) for t in long_fetch_needed],
                return_exceptions=True,
            )
            for t, frame in zip(long_fetch_needed, long_results):
                if not isinstance(frame, Exception) and frame is not None and not frame.empty:
                    price_data[t] = frame

    # Get USD/INR rate and live prices for weight computation
    usd_inr = await fetcher.get_usd_inr_rate()
    live_prices_inr = {}
    if hasattr(fetcher, "get_latest_prices_in_inr"):
        try:
            live_prices_inr = await fetcher.get_latest_prices_in_inr(
                [
                    {
                        "ticker": ticker,
                        "source": asset_map[ticker]["data_source"],
                        "exchange": asset_map[ticker].get("exchange"),
                        "currency": asset_currencies[ticker],
                    }
                    for ticker in tickers
                ]
            )
        except Exception:
            live_prices_inr = {}

    # Compute current values in INR for each holding
    current_values_inr: dict[str, float] = {}
    for ticker in tickers:
        live_price_inr = live_prices_inr.get(ticker)
        if live_price_inr is not None:
            current_values_inr[ticker] = float(live_price_inr) * quantities[ticker]
            continue
        frame = price_data.get(ticker)
        if frame is None or frame.empty:
            continue
        price = float(frame["close"].iloc[-1])
        currency = asset_currencies.get(ticker, "USD").upper()
        if currency == "USD":
            price_inr = price * usd_inr
        else:
            price_inr = price
        current_values_inr[ticker] = price_inr * quantities[ticker]

    total_value_inr = sum(current_values_inr.values())
    if total_value_inr <= 0:
        raise AppError("Stress test failed", "invalid_portfolio_value", "Portfolio value must be positive", 400)

    # Build holdings list for stress engine
    stress_holdings = []
    for ticker in tickers:
        if ticker not in current_values_inr:
            continue
        asset_class_raw = asset_map[ticker].get("asset_class")
        # asset_class may be an enum value or string
        asset_class_str = asset_class_raw.value if hasattr(asset_class_raw, "value") else str(asset_class_raw)
        stress_holdings.append({
            "ticker": ticker,
            "weight": current_values_inr[ticker] / total_value_inr,
            "asset_class": asset_class_str,
            "value_inr": current_values_inr[ticker],
            "currency": asset_currencies.get(ticker, "USD"),
        })

    # Run each historical scenario (with per-scenario error isolation)
    historical_results: list[ScenarioResultOut] = []
    for scenario in HISTORICAL_SCENARIOS:
        try:
            result = compute_historical_scenario(
                scenario=scenario,
                holdings=stress_holdings,
                price_data=price_data,
                portfolio_value_inr=total_value_inr,
            )
            historical_results.append(
                ScenarioResultOut(
                    scenario_name=result.scenario_name,
                    scenario_label=result.scenario_label,
                    scenario_start=result.scenario_start,
                    scenario_end=result.scenario_end,
                    portfolio_return_pct=result.portfolio_return_pct,
                    portfolio_inr_impact=result.portfolio_inr_impact,
                    per_holding=[
                        HoldingImpactOut(
                            ticker=h.ticker,
                            asset_class=h.asset_class,
                            weight=h.weight,
                            scenario_return_pct=h.scenario_return_pct,
                            portfolio_contribution_pct=h.portfolio_contribution_pct,
                            is_proxy=h.is_proxy,
                            proxy_ticker=h.proxy_ticker,
                        )
                        for h in result.per_holding
                    ],
                )
            )
        except Exception as exc:
            # Include a zero-impact placeholder with an error flag
            historical_results.append(
                ScenarioResultOut(
                    scenario_name=scenario["name"],
                    scenario_label=f"{scenario['label']} (error: {exc})",
                    scenario_start=scenario["start"],
                    scenario_end=scenario["end"],
                    portfolio_return_pct=0.0,
                    portfolio_inr_impact=0.0,
                    per_holding=[],
                )
            )

    return StressTestResponse(
        portfolio_value_inr=total_value_inr,
        historical_scenarios=historical_results,
        custom_shock=None,
    )


async def run_custom_stress(
    portfolio_id: UUID,
    user_id: UUID,
    db: AsyncSession,
    fetcher: DataFetcher,
    shock: CustomShockRequest,
) -> dict:
    _, holdings, assets = await load_portfolio_snapshot(portfolio_id, user_id, db)
    if not holdings:
        raise AppError("Custom stress failed", "empty_portfolio", "Portfolio has no holdings", 400)

    asset_map = {row["ticker"]: row for row in assets}
    tickers = [row["ticker"] for row in holdings if row["ticker"] in asset_map]
    quantities = {row["ticker"]: float(row["quantity"]) for row in holdings}
    asset_currencies = {ticker: asset_map[ticker]["currency"] for ticker in tickers}

    # Fetch recent prices (5 days is enough for current weights)
    price_results = await asyncio.gather(
        *[fetcher.get_price_history(ticker, asset_map[ticker]["data_source"], days=10) for ticker in tickers],
        return_exceptions=True,
    )
    price_data = {
        ticker: frame
        for ticker, frame in zip(tickers, price_results)
        if not isinstance(frame, Exception) and not frame.empty
    }

    usd_inr = await fetcher.get_usd_inr_rate()

    current_values_inr: dict[str, float] = {}
    for ticker in tickers:
        frame = price_data.get(ticker)
        if frame is None or frame.empty:
            continue
        price = float(frame["close"].iloc[-1])
        currency = asset_currencies.get(ticker, "USD").upper()
        price_inr = price * usd_inr if currency == "USD" else price
        current_values_inr[ticker] = price_inr * quantities[ticker]

    total_value_inr = sum(current_values_inr.values())
    if total_value_inr <= 0:
        raise AppError("Custom stress failed", "invalid_portfolio_value", "Portfolio value must be positive", 400)

    stress_holdings = []
    for ticker in tickers:
        if ticker not in current_values_inr:
            continue
        asset_class_raw = asset_map[ticker].get("asset_class")
        asset_class_str = asset_class_raw.value if hasattr(asset_class_raw, "value") else str(asset_class_raw)
        stress_holdings.append({
            "ticker": ticker,
            "weight": current_values_inr[ticker] / total_value_inr,
            "asset_class": asset_class_str,
            "value_inr": current_values_inr[ticker],
            "currency": asset_currencies.get(ticker, "USD"),
        })

    result = compute_custom_shock(
        holdings=stress_holdings,
        portfolio_value_inr=total_value_inr,
        equities_pct=shock.equities_pct,
        crypto_pct=shock.crypto_pct,
        gold_pct=shock.gold_pct,
        bonds_pct=shock.bonds_pct,
        inr_move_pct=shock.inr_move_pct,
    )
    result["portfolio_value_inr"] = total_value_inr
    return result
