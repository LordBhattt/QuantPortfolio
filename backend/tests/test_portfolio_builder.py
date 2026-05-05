from backend.services.portfolio_builder import build_recommended_portfolio


def test_build_recommended_portfolio_conservative() -> None:
    result = build_recommended_portfolio(2, 100000)

    assert result[0] == {
        "ticker": "LIQUIDBEES.NS",
        "asset_class": "bond",
        "recommended_weight": 0.5,
        "recommended_amount_inr": 50000.0,
    }
    assert round(sum(item["recommended_weight"] for item in result), 10) == 1.0


def test_build_recommended_portfolio_aggressive_crypto_split() -> None:
    result = build_recommended_portfolio(9, 100000)

    crypto = [item for item in result if item["asset_class"] == "crypto"]
    assert [item["ticker"] for item in crypto] == ["BTC", "ETH", "BNB"]
    assert [item["recommended_weight"] for item in crypto] == [0.18, 0.09, 0.03]