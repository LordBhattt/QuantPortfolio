"""Reproducible market-data universe and documented proxy mappings."""

UNIVERSE: tuple[str, ...] = (
    "SPY", "QQQ", "IWM", "EFA", "EEM", "TLT", "IEF", "AGG", "LQD", "HYG",
    "GLD", "SLV", "DBC", "VNQ",
    "RELIANCE.NS", "HDFCBANK.NS", "TCS.NS", "INFY.NS", "ICICIBANK.NS",
    "KOTAKBANK.NS", "HINDUNILVR.NS", "ITC.NS", "LT.NS", "AXISBANK.NS",
    "SBIN.NS", "MARUTI.NS", "NESTLEIND.NS", "WIPRO.NS", "NIFTYBEES.NS",
    "GOLDBEES.NS", "BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD",
    "AAPL", "MSFT", "AMZN", "GOOGL", "NVDA", "META", "JPM", "XOM",
    "JNJ", "PG", "KO", "PEP", "V", "MA", "UNH", "HD", "COST", "CAT",
    "BA", "DIS", "CSCO", "ADBE", "ORCL", "CRM", "NFLX", "INTC",
)

# The seeded Indian bond symbol is not listed on Yahoo. TLT is used only as
# a reproducible liquid bond proxy and must be labelled as such in reports/UI.
PROXIES: dict[str, str] = {"LTGILTDIR.NS": "TLT"}
