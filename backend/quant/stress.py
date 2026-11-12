"""Historical scenario and custom shock stress testing."""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Optional

HISTORICAL_SCENARIOS = [
    {
        "name": "GFC",
        "label": "Global Financial Crisis",
        "start": "2008-09-01",
        "end": "2009-03-09",
    },
    {
        "name": "COVID",
        "label": "COVID Crash",
        "start": "2020-02-19",
        "end": "2020-03-23",
    },
    {
        "name": "RATE_HIKES_2022",
        "label": "2022 Rate Hike Cycle",
        "start": "2022-01-03",
        "end": "2022-10-12",
    },
]

# Asset-class proxies when holding history is missing in scenario window
PROXY_MAP = {
    "stock": "SPY",
    "mf_etf": "SPY",
    "crypto": "BTC-USD",
    "gold": "GLD",
    "bond": "AGG",
}


@dataclass
class HoldingImpact:
    ticker: str
    asset_class: str
    weight: float
    scenario_return_pct: float  # holding's return in the scenario window
    portfolio_contribution_pct: float  # weight * scenario_return_pct
    is_proxy: bool  # True if proxy was used instead of actual history
    proxy_ticker: Optional[str]  # which proxy was used


@dataclass
class ScenarioResult:
    scenario_name: str
    scenario_label: str
    scenario_start: str
    scenario_end: str
    portfolio_return_pct: float
    portfolio_inr_impact: float  # negative = loss
    per_holding: list[HoldingImpact]


def compute_historical_scenario(
    scenario: dict,
    holdings: list[dict],  # [{ticker, weight, asset_class, value_inr}]
    price_data: dict[str, pd.DataFrame],  # pre-fetched price data for the scenario window
    portfolio_value_inr: float,
) -> ScenarioResult:
    """
    Compute portfolio impact in a historical scenario window.
    For each holding, find its return in the scenario window.
    If the holding doesn't have data in that window, use an asset-class proxy.
    """
    per_holding = []
    total_return = 0.0

    for h in holdings:
        ticker = h["ticker"]
        weight = h["weight"]
        asset_class = h["asset_class"]

        # Try actual holding data first
        df = price_data.get(ticker)
        is_proxy = False
        proxy_ticker = None
        scenario_ret = None

        if df is not None and not df.empty:
            # Filter to scenario window
            start = pd.Timestamp(scenario["start"])
            end = pd.Timestamp(scenario["end"])
            window = df[(df.index >= start) & (df.index <= end)]
            if len(window) >= 2:
                # Return = last price / first price - 1
                scenario_ret = float(window["close"].iloc[-1] / window["close"].iloc[0] - 1)

        # Fall back to proxy if needed
        if scenario_ret is None:
            proxy_ticker = PROXY_MAP.get(asset_class, "SPY")
            is_proxy = True
            proxy_df = price_data.get(proxy_ticker)
            if proxy_df is not None and not proxy_df.empty:
                start = pd.Timestamp(scenario["start"])
                end = pd.Timestamp(scenario["end"])
                window = proxy_df[(proxy_df.index >= start) & (proxy_df.index <= end)]
                if len(window) >= 2:
                    scenario_ret = float(window["close"].iloc[-1] / window["close"].iloc[0] - 1)
            if scenario_ret is None:
                scenario_ret = 0.0  # last resort: no impact

        contribution = weight * scenario_ret
        total_return += contribution

        per_holding.append(HoldingImpact(
            ticker=ticker,
            asset_class=asset_class,
            weight=weight,
            scenario_return_pct=scenario_ret * 100,
            portfolio_contribution_pct=contribution * 100,
            is_proxy=is_proxy,
            proxy_ticker=proxy_ticker,
        ))

    return ScenarioResult(
        scenario_name=scenario["name"],
        scenario_label=scenario["label"],
        scenario_start=scenario["start"],
        scenario_end=scenario["end"],
        portfolio_return_pct=total_return * 100,
        portfolio_inr_impact=total_return * portfolio_value_inr,
        per_holding=per_holding,
    )


def compute_custom_shock(
    holdings: list[dict],  # [{ticker, weight, asset_class, value_inr}]
    portfolio_value_inr: float,
    equities_pct: float = 0.0,  # shock in %
    crypto_pct: float = 0.0,
    gold_pct: float = 0.0,
    bonds_pct: float = 0.0,
    inr_move_pct: float = 0.0,  # INR depreciation/appreciation vs USD
) -> dict:
    """Apply custom shocks to each asset class."""
    shock_map = {
        "stock": equities_pct / 100,
        "mf_etf": equities_pct / 100,
        "crypto": crypto_pct / 100,
        "gold": gold_pct / 100,
        "bond": bonds_pct / 100,
    }

    per_holding = []
    total_return = 0.0

    for h in holdings:
        base_shock = shock_map.get(h["asset_class"], 0.0)
        # USD-priced assets (crypto, gold ETF in USD) also affected by INR move
        # If INR weakens (positive inr_move_pct), USD assets gain in INR terms
        fx_adjustment = 0.0
        if h.get("currency") in ("USD", "usd"):
            fx_adjustment = inr_move_pct / 100

        total_shock = base_shock + fx_adjustment
        contribution = h["weight"] * total_shock
        total_return += contribution

        per_holding.append({
            "ticker": h["ticker"],
            "asset_class": h["asset_class"],
            "weight": h["weight"],
            "shock_pct": total_shock * 100,
            "portfolio_contribution_pct": contribution * 100,
        })

    return {
        "portfolio_return_pct": total_return * 100,
        "portfolio_inr_impact": total_return * portfolio_value_inr,
        "per_holding": per_holding,
    }
