"""Stress test service - orchestrates historical scenario and custom shock tests."""

import asyncio
from uuid import UUID

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

# Days of history needed to cover GFC window starting 2008-09-01
# We fetch from 2007-01-01 to have buffer for price-at-start lookups
_STRESS_HISTORY_DAYS = 6500  # ~18 years covers 2007 onwards

# Proxy tickers always needed for scenario proxying
_PROXY_TICKERS = list(set(PROXY_MAP.values()))  # SPY, BTC-USD, GLD, AGG


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

    # Fetch long price history for all holdings + proxies
    all_tickers_to_fetch = list(set(tickers + _PROXY_TICKERS))
    price_results = await asyncio.gather(
        *[fetcher.get_price_history(t, "yahoo", days=_STRESS_HISTORY_DAYS) for t in all_tickers_to_fetch],
        return_exceptions=True,
    )
    price_data = {
        ticker: frame
        for ticker, frame in zip(all_tickers_to_fetch, price_results)
        if not isinstance(frame, Exception) and not frame.empty
    }

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
