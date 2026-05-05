from __future__ import annotations


def build_recommended_portfolio(risk_score: int, investment_amount: float) -> list[dict[str, float | str]]:
    if risk_score <= 3:
        allocations = [
            ("LIQUIDBEES.NS", "bond", 0.50),
            ("NIFTYBEES.NS", "stock", 0.15),
            ("HDFCBANK.NS", "stock", 0.15),
            ("GOLDBEES.NS", "gold", 0.15),
            ("BTC", "crypto", 0.05),
        ]
    elif risk_score <= 6:
        allocations = [
            ("LIQUIDBEES.NS", "bond", 0.30),
            ("RELIANCE.NS", "stock", 0.10),
            ("TCS.NS", "stock", 0.10),
            ("INFY.NS", "stock", 0.10),
            ("NIFTYBEES.NS", "stock", 0.10),
            ("GOLDBEES.NS", "gold", 0.15),
            ("BTC", "crypto", 0.075),
            ("ETH", "crypto", 0.075),
        ]
    else:
        allocations = [
            ("LIQUIDBEES.NS", "bond", 0.10),
            ("RELIANCE.NS", "stock", 0.10),
            ("TCS.NS", "stock", 0.10),
            ("INFY.NS", "stock", 0.10),
            ("HDFCBANK.NS", "stock", 0.10),
            ("WIPRO.NS", "stock", 0.10),
            ("GOLDBEES.NS", "gold", 0.10),
            ("BTC", "crypto", 0.18),
            ("ETH", "crypto", 0.09),
            ("BNB", "crypto", 0.03),
        ]

    return [
        {
            "ticker": ticker,
            "asset_class": asset_class,
            "recommended_weight": weight,
            "recommended_amount_inr": round(investment_amount * weight, 2),
        }
        for ticker, asset_class, weight in allocations
    ]