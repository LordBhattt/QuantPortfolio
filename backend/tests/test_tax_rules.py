from datetime import date

import pytest

from backend.quant.tax_rules import TaxYearTracker, is_long_term


def test_equity_short_term_vs_long_term_rate_differs() -> None:
    tracker = TaxYearTracker()

    short = tracker.record_disposal("stock", date(2024, 1, 1), date(2024, 6, 1), gross_gain=10_000.0)
    assert short.is_long_term is False
    assert short.tax_rate == 0.20
    assert short.tax_owed == pytest.approx(2_000.0)

    tracker2 = TaxYearTracker()
    long = tracker2.record_disposal("stock", date(2020, 1, 1), date(2024, 6, 1), gross_gain=10_000.0)
    assert long.is_long_term is True
    assert long.tax_rate == 0.125
    # under the Rs 1.25L annual exemption, so fully exempt
    assert long.tax_owed == pytest.approx(0.0)


def test_equity_ltcg_exemption_is_an_aggregate_annual_threshold_not_per_trade() -> None:
    tracker = TaxYearTracker()
    acquired = date(2020, 1, 1)

    first = tracker.record_disposal("stock", acquired, date(2024, 6, 1), gross_gain=100_000.0)
    assert first.tax_owed == pytest.approx(0.0)  # within Rs 1.25L exemption

    second = tracker.record_disposal("stock", acquired, date(2024, 7, 1), gross_gain=100_000.0)
    # cumulative 200,000 this FY -> only the 75,000 over the 125,000 exemption is taxable
    assert second.taxable_gain == pytest.approx(75_000.0)
    assert second.tax_owed == pytest.approx(75_000.0 * 0.125)


def test_crypto_gain_always_taxed_flat_30_percent_regardless_of_holding_period() -> None:
    tracker = TaxYearTracker()

    quick = tracker.record_disposal("crypto", date(2024, 1, 1), date(2024, 1, 10), gross_gain=1_000.0)
    slow = tracker.record_disposal("crypto", date(2018, 1, 1), date(2024, 1, 10), gross_gain=1_000.0)

    assert quick.tax_rate == 0.30
    assert slow.tax_rate == 0.30
    assert quick.tax_owed == pytest.approx(300.0)
    assert slow.tax_owed == pytest.approx(300.0)
    assert quick.is_long_term is False
    assert slow.is_long_term is False  # the LT/ST distinction does not exist for crypto


def test_crypto_loss_provides_zero_tax_benefit_anywhere() -> None:
    """The structural case this whole module exists to capture: a crypto
    loss cannot offset another crypto gain, or an equity gain, or anything
    else -- unlike every other asset class here."""
    tracker = TaxYearTracker()

    loss = tracker.record_disposal("crypto", date(2024, 1, 1), date(2024, 6, 1), gross_gain=-5_000.0)
    assert loss.tax_owed == pytest.approx(0.0)

    other_crypto_gain = tracker.record_disposal("crypto", date(2024, 1, 1), date(2024, 6, 2), gross_gain=5_000.0)
    assert other_crypto_gain.tax_owed == pytest.approx(5_000.0 * 0.30)  # undiminished by the earlier loss

    equity_gain = tracker.record_disposal("stock", date(2020, 1, 1), date(2024, 6, 3), gross_gain=200_000.0)
    # still only reduced by the exemption, not by the crypto loss
    assert equity_gain.taxable_gain == pytest.approx(200_000.0 - 125_000.0)


def test_short_term_capital_loss_offsets_both_short_and_long_term_equity_gains() -> None:
    tracker = TaxYearTracker()

    tracker.record_disposal("stock", date(2024, 1, 1), date(2024, 3, 1), gross_gain=-4_000.0)  # STCL, FY23-24
    gain = tracker.record_disposal("stock", date(2020, 1, 1), date(2024, 3, 15), gross_gain=200_000.0)  # LTCG, same FY23-24

    # STCL offsets the LTCG first, then the Rs 1.25L exemption applies to the remainder
    assert gain.taxable_gain == pytest.approx(200_000.0 - 4_000.0 - 125_000.0)


def test_long_term_capital_loss_does_not_offset_short_term_gains() -> None:
    tracker = TaxYearTracker()

    tracker.record_disposal("stock", date(2018, 1, 1), date(2024, 1, 1), gross_gain=-10_000.0)  # LTCL
    short_gain = tracker.record_disposal("stock", date(2024, 1, 1), date(2024, 3, 1), gross_gain=8_000.0)  # STCG

    assert short_gain.taxable_gain == pytest.approx(8_000.0)  # untouched by the LTCL
    assert short_gain.tax_owed == pytest.approx(8_000.0 * 0.20)


def test_bond_is_always_taxed_at_slab_rate_regardless_of_holding_period() -> None:
    tracker = TaxYearTracker()

    short = tracker.record_disposal("bond", date(2024, 1, 1), date(2024, 3, 1), gross_gain=1_000.0)
    long = tracker.record_disposal("bond", date(2015, 1, 1), date(2024, 3, 1), gross_gain=1_000.0)

    assert short.tax_rate == long.tax_rate == 0.30
    assert short.is_long_term is False
    assert long.is_long_term is False  # debt funds never qualify for LTCG treatment


def test_fiscal_year_rollover_resets_exemption_and_carried_losses() -> None:
    tracker = TaxYearTracker()

    tracker.record_disposal("stock", date(2020, 1, 1), date(2024, 3, 20), gross_gain=125_000.0)  # uses up FY23-24 exemption
    tracker.record_disposal("stock", date(2024, 1, 1), date(2024, 3, 25), gross_gain=-2_000.0)  # STCL carried in FY23-24

    # a new fiscal year starts 1 April -- exemption and carried loss both reset
    next_fy_gain = tracker.record_disposal("stock", date(2020, 1, 1), date(2024, 4, 5), gross_gain=100_000.0)
    assert next_fy_gain.taxable_gain == pytest.approx(0.0)  # fresh Rs 1.25L exemption, not reduced by the old STCL


@pytest.mark.parametrize(
    "asset_class,days,expected",
    [
        ("stock", 364, False),
        ("stock", 365, True),
        ("gold", 729, False),
        ("gold", 730, True),
        ("bond", 10_000, False),
        ("crypto", 10_000, False),
    ],
)
def test_is_long_term_thresholds(asset_class: str, days: int, expected: bool) -> None:
    assert is_long_term(asset_class, days) is expected
