from datetime import date

import pytest

from backend.quant.tax_lot_ledger import (
    Lot,
    PortfolioLedger,
    rebalance_to_target,
    select_lots_fifo,
    select_lots_tax_aware,
)
from backend.quant.tax_rules import TaxYearTracker


def test_select_lots_fifo_picks_oldest_lot_first() -> None:
    lots = [
        Lot("AAA", "stock", 10, 100.0, date(2023, 6, 1)),
        Lot("AAA", "stock", 10, 100.0, date(2022, 1, 1)),
    ]
    chosen = select_lots_fifo(lots, quantity_to_sell=5, current_price=150.0, as_of=date(2024, 1, 1))
    assert chosen[0][0].acquired_on == date(2022, 1, 1)
    assert chosen[0][1] == pytest.approx(5)


def test_select_lots_tax_aware_prefers_loss_lots_first() -> None:
    lots = [
        Lot("AAA", "stock", 10, 200.0, date(2020, 1, 1)),  # would be a loss at price 150
        Lot("AAA", "stock", 10, 50.0, date(2023, 6, 1)),  # would be a gain at price 150
    ]
    chosen = select_lots_tax_aware(lots, quantity_to_sell=5, current_price=150.0, as_of=date(2024, 1, 1))
    assert chosen[0][0].cost_basis_price == 200.0  # the loss lot, sold first


def test_select_lots_tax_aware_prefers_ltcg_over_stcg_when_all_gains() -> None:
    lots = [
        Lot("AAA", "stock", 10, 50.0, date(2020, 1, 1)),  # long-term gain
        Lot("AAA", "stock", 10, 50.0, date(2023, 12, 1)),  # short-term gain
    ]
    chosen = select_lots_tax_aware(lots, quantity_to_sell=5, current_price=150.0, as_of=date(2024, 1, 1))
    assert chosen[0][0].acquired_on == date(2020, 1, 1)  # LTCG lot preferred


def test_select_lots_tax_aware_defers_larger_crypto_gains() -> None:
    lots = [
        Lot("BTC", "crypto", 1, 1_000.0, date(2020, 1, 1)),  # huge gain at price 50,000
        Lot("BTC", "crypto", 1, 45_000.0, date(2023, 1, 1)),  # small gain
    ]
    chosen = select_lots_tax_aware(lots, quantity_to_sell=1, current_price=50_000.0, as_of=date(2024, 1, 1))
    assert chosen[0][0].cost_basis_price == 45_000.0  # smaller gain sold first, big gain deferred


def test_ledger_buy_creates_lot_and_reduces_cash() -> None:
    ledger = PortfolioLedger(cash=10_000.0)
    ledger.buy("AAA", "stock", 10, 100.0, date(2024, 1, 1))
    assert ledger.cash == pytest.approx(9_000.0)
    assert len(ledger.lots["AAA"]) == 1
    assert ledger.lots["AAA"][0].quantity == 10


def test_ledger_sell_realizes_gain_and_applies_tax() -> None:
    ledger = PortfolioLedger(cash=0.0)
    ledger.buy("AAA", "stock", 10, 100.0, date(2020, 1, 1))
    tracker = TaxYearTracker()

    disposals = ledger.sell("AAA", 10, 500.0, date(2024, 6, 1), tracker, policy="fifo")

    assert len(disposals) == 1
    gross_gain = disposals[0].gross_gain
    assert gross_gain == pytest.approx((500.0 - 100.0) * 10)
    # long-term equity gain, fully within the Rs 1.25L exemption -> zero tax
    assert disposals[0].tax_owed == pytest.approx(0.0)
    assert ledger.lots.get("AAA", []) == []  # lot fully exhausted and removed


def test_ledger_sell_with_apply_tax_false_owes_nothing() -> None:
    ledger = PortfolioLedger(cash=0.0)
    ledger.buy("AAA", "crypto", 10, 100.0, date(2024, 1, 1))
    tracker = TaxYearTracker()

    disposals = ledger.sell("AAA", 10, 500.0, date(2024, 3, 1), tracker, policy="fifo", apply_tax=False)

    assert disposals[0].gross_gain == pytest.approx((500.0 - 100.0) * 10)
    assert disposals[0].tax_owed == pytest.approx(0.0)
    # cash = -cost_of_buy + full_sale_proceeds (no tax subtracted)
    assert ledger.cash == pytest.approx(-100.0 * 10 + 500.0 * 10)


def test_ledger_sell_partial_quantity_splits_across_lots() -> None:
    ledger = PortfolioLedger(cash=0.0)
    ledger.buy("AAA", "stock", 5, 100.0, date(2020, 1, 1))
    ledger.buy("AAA", "stock", 5, 100.0, date(2021, 1, 1))
    tracker = TaxYearTracker()

    ledger.sell("AAA", 7, 150.0, date(2024, 1, 1), tracker, policy="fifo")

    remaining = ledger.lots["AAA"]
    assert len(remaining) == 1
    assert remaining[0].quantity == pytest.approx(3)
    assert remaining[0].acquired_on == date(2021, 1, 1)


def test_rebalance_to_target_generates_correct_trades() -> None:
    ledger = PortfolioLedger(cash=1_000.0)
    ledger.buy("AAA", "stock", 10, 100.0, date(2020, 1, 1))  # worth 1000 at price 100, cash now 0
    tracker = TaxYearTracker()
    prices = {"AAA": 100.0, "BBB": 50.0}

    rebalance_to_target(
        ledger,
        target_weights={"AAA": 0.5, "BBB": 0.5},
        asset_classes={"AAA": "stock", "BBB": "stock"},
        prices=prices,
        on_date=date(2024, 1, 1),
        tracker=tracker,
        policy="fifo",
    )

    aaa_value = sum(lot.quantity for lot in ledger.lots.get("AAA", [])) * prices["AAA"]
    bbb_value = sum(lot.quantity for lot in ledger.lots.get("BBB", [])) * prices["BBB"]
    total = ledger.holdings_value(prices)
    assert aaa_value / total == pytest.approx(0.5, abs=0.02)
    assert bbb_value / total == pytest.approx(0.5, abs=0.02)


def test_tax_aware_rebalance_pays_less_tax_than_fifo_when_a_loss_lot_exists() -> None:
    """The decisive comparison: a portfolio needs to trim its crypto
    allocation. The OLDER lot happens to be deep in the green, the NEWER
    lot deep in the red. FIFO blindly sells whichever is older -- here,
    the gain lot -- and pays real tax on a disposal it could have
    avoided. The tax-aware policy finds the free (loss) lot regardless of
    its age and pays nothing on this trade."""

    def build_ledger() -> PortfolioLedger:
        ledger = PortfolioLedger(cash=0.0)
        ledger.buy("BTC", "crypto", 1.0, 10_000.0, date(2022, 1, 1))  # older, now a big gain at 50,000
        ledger.buy("BTC", "crypto", 1.0, 60_000.0, date(2023, 1, 1))  # newer, now a loss at 50,000
        return ledger

    price = 50_000.0
    sell_quantity = 1.0
    as_of = date(2024, 1, 1)

    fifo_ledger = build_ledger()
    fifo_tracker = TaxYearTracker()
    fifo_disposals = fifo_ledger.sell("BTC", sell_quantity, price, as_of, fifo_tracker, policy="fifo")
    fifo_tax = sum(d.tax_owed for d in fifo_disposals)

    aware_ledger = build_ledger()
    aware_tracker = TaxYearTracker()
    aware_disposals = aware_ledger.sell("BTC", sell_quantity, price, as_of, aware_tracker, policy="tax_aware")
    aware_tax = sum(d.tax_owed for d in aware_disposals)

    assert fifo_tax == pytest.approx((50_000.0 - 10_000.0) * 0.30)  # FIFO sold the older gain lot
    assert aware_tax == pytest.approx(0.0)  # tax-aware sold the loss lot instead
    assert aware_tax < fifo_tax
