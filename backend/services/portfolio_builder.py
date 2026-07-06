from __future__ import annotations


def build_recommended_portfolio(risk_score: int, investment_amount: float) -> list[dict[str, float | str]]:
    if risk_score <= 3:
        allocations = [
            ("LIQUIDBEES.NS", "bond", 0.45),
            ("NIFTYBEES.NS", "mf_etf", 0.20),
            ("GOLDBEES.NS", "gold", 0.15),
            ("HDFCBANK.NS", "stock", 0.10),
            ("RELIANCE.NS", "stock", 0.08),
            ("BTC", "crypto", 0.02),
        ]
    elif risk_score <= 6:
        allocations = [
            ("LIQUIDBEES.NS", "bond", 0.30),
            ("NIFTYBEES.NS", "mf_etf", 0.20),
            ("RELIANCE.NS", "stock", 0.10),
            ("TCS.NS", "stock", 0.10),
            ("INFY.NS", "stock", 0.10),
            ("GOLDBEES.NS", "gold", 0.10),
            ("BTC", "crypto", 0.05),
            ("ETH", "crypto", 0.05),
        ]
    else:
        allocations = [
            ("LIQUIDBEES.NS", "bond", 0.15),
            ("NIFTYBEES.NS", "mf_etf", 0.15),
            ("RELIANCE.NS", "stock", 0.14),
            ("TCS.NS", "stock", 0.12),
            ("INFY.NS", "stock", 0.11),
            ("HDFCBANK.NS", "stock", 0.05),
            ("WIPRO.NS", "stock", 0.03),
            ("GOLDBEES.NS", "gold", 0.10),
            ("BTC", "crypto", 0.08),
            ("ETH", "crypto", 0.05),
            ("BNB", "crypto", 0.02),
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