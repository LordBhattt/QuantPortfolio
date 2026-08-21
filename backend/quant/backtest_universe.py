"""Fixed multi-asset universe shared by the dataset cache builder and the
backtest service, so both always agree on which tickers/classes/currencies
make up the backtest study."""

from dataclasses import dataclass


@dataclass(frozen=True)
class UniverseAsset:
    ticker: str
    source: str
    currency: str
    asset_class: str


BACKTEST_UNIVERSE: list[UniverseAsset] = [
    UniverseAsset("AAPL", "yahoo", "USD", "stock"),
    UniverseAsset("MSFT", "yahoo", "USD", "stock"),
    UniverseAsset("GOOGL", "yahoo", "USD", "stock"),
    UniverseAsset("AMZN", "yahoo", "USD", "stock"),
    UniverseAsset("SPY", "yahoo", "USD", "mf_etf"),
    UniverseAsset("QQQ", "yahoo", "USD", "mf_etf"),
    UniverseAsset("RELIANCE.NS", "yahoo", "INR", "stock"),
    UniverseAsset("TCS.NS", "yahoo", "INR", "stock"),
    UniverseAsset("HDFCBANK.NS", "yahoo", "INR", "stock"),
    UniverseAsset("NIFTYBEES.NS", "yahoo", "INR", "mf_etf"),
    UniverseAsset("GLD", "yahoo", "USD", "gold"),
    UniverseAsset("IAU", "yahoo", "USD", "gold"),
    UniverseAsset("TLT", "yahoo", "USD", "bond"),
    UniverseAsset("BND", "yahoo", "USD", "bond"),
    UniverseAsset("bitcoin", "coingecko", "USD", "crypto"),
    UniverseAsset("ethereum", "coingecko", "USD", "crypto"),
]
