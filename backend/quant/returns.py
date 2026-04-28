"""Return computation and FX normalization helpers."""

from typing import Dict

import numpy as np
import pandas as pd


def log_returns(prices: pd.Series) -> pd.Series:
    return np.log(prices / prices.shift(1)).dropna()


def align_returns(
    price_data: Dict[str, pd.DataFrame],
    asset_currencies: Dict[str, str],
    base_currency: str = "USD",
    usd_inr_rate: float = 83.5,
) -> pd.DataFrame:
    series_dict: dict[str, pd.Series] = {}
    target_currency = base_currency.upper()

    for ticker, frame in price_data.items():
        prices = frame["close"].astype(float).copy()
        native = asset_currencies.get(ticker, "USD").upper()
        if native == "INR" and target_currency == "USD":
            prices = prices / usd_inr_rate
        elif native == "USD" and target_currency == "INR":
            prices = prices * usd_inr_rate
        returns = log_returns(prices)
        if not returns.empty:
            series_dict[ticker] = returns

    if not series_dict:
        return pd.DataFrame()
    return pd.DataFrame(series_dict).dropna(how="any")


def annualise_returns(daily_returns: pd.Series, trading_days: int = 252) -> float:
    return float(daily_returns.mean() * trading_days)


def annualise_volatility(daily_returns: pd.Series, trading_days: int = 252) -> float:
    return float(daily_returns.std() * np.sqrt(trading_days))
