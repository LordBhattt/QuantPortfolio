"""Lot-level portfolio ledger and tax-aware trade execution.

The rest of the backtest engine works in "return space" -- a weight vector
per rebalance date. To actually measure tax drag we need to simulate a
real position ledger: individual tax lots with a quantity, acquisition
date, and cost basis, since Indian capital gains tax depends on exactly
which lot you sell, not just how much.

Two lot-selection policies are provided for the same target-weight
rebalance: `select_lots_fifo` (oldest lot first -- what most brokerage/
platform default behavior does, and what a tax-blind rebalancer would
produce) and `select_lots_tax_aware` (ranks lots by their tax cost right
now, given backend/quant/tax_rules.py). Both are myopic/greedy rankings
computed lot-by-lot rather than a full combinatorial reallocation across
the whole trade -- the same simplification real tax-loss-harvesting
engines make, and enough to expose the structural effect this module
exists to measure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from backend.quant.tax_rules import (
    DEFAULT_SLAB_RATE,
    LONG_TERM_RATES,
    SHORT_TERM_RATES,
    TaxYearTracker,
    holding_period_days,
    is_long_term,
)

MIN_TRADE_VALUE = 1e-6
MIN_LOT_QUANTITY = 1e-9


@dataclass
class Lot:
    ticker: str
    asset_class: str
    quantity: float
    cost_basis_price: float
    acquired_on: date


@dataclass
class Disposal:
    ticker: str
    quantity: float
    proceeds: float
    gross_gain: float
    tax_owed: float


def _lot_priority_key(lot: Lot, current_price: float, as_of: date) -> tuple:
    """Lower = sell this lot first under the tax-aware policy."""
    gross_gain = (current_price - lot.cost_basis_price) * lot.quantity
    if gross_gain <= 0:
        # Realizing a loss costs nothing in tax this trade (and for every
        # non-crypto class it also banks an offset credit for later gains),
        # so losses are always the cheapest lots to sell.
        return (0, lot.acquired_on)
    if lot.asset_class == "crypto":
        # Sec 115BBH: flat 30% regardless of holding period. No LTCG relief
        # to prefer, so just defer the largest gains -- sell the smallest
        # taxable gain first.
        return (1, gross_gain, lot.acquired_on)
    holding_days = holding_period_days(lot.acquired_on, as_of)
    long_term = is_long_term(lot.asset_class, holding_days)
    rate = (LONG_TERM_RATES if long_term else SHORT_TERM_RATES).get(lot.asset_class, DEFAULT_SLAB_RATE)
    return (2, rate, gross_gain, lot.acquired_on)


def _fill_from_ordered(ordered_lots: list[Lot], quantity_to_sell: float) -> list[tuple[Lot, float]]:
    remaining = quantity_to_sell
    filled: list[tuple[Lot, float]] = []
    for lot in ordered_lots:
        if remaining <= MIN_LOT_QUANTITY:
            break
        take = min(lot.quantity, remaining)
        if take <= 0:
            continue
        filled.append((lot, take))
        remaining -= take
    return filled


def select_lots_fifo(lots: list[Lot], quantity_to_sell: float, current_price: float, as_of: date) -> list[tuple[Lot, float]]:
    del current_price, as_of
    ordered = sorted(lots, key=lambda lot: lot.acquired_on)
    return _fill_from_ordered(ordered, quantity_to_sell)


def select_lots_tax_aware(lots: list[Lot], quantity_to_sell: float, current_price: float, as_of: date) -> list[tuple[Lot, float]]:
    ordered = sorted(lots, key=lambda lot: _lot_priority_key(lot, current_price, as_of))
    return _fill_from_ordered(ordered, quantity_to_sell)


LOT_SELECTORS = {
    "fifo": select_lots_fifo,
    "tax_aware": select_lots_tax_aware,
}


@dataclass
class PortfolioLedger:
    lots: dict[str, list[Lot]] = field(default_factory=dict)
    cash: float = 0.0

    def holdings_value(self, prices: dict[str, float]) -> float:
        total = self.cash
        for ticker, ticker_lots in self.lots.items():
            price = prices.get(ticker, 0.0)
            total += sum(lot.quantity for lot in ticker_lots) * price
        return total

    def buy(self, ticker: str, asset_class: str, quantity: float, price: float, on_date: date) -> None:
        if quantity <= 0 or price <= 0:
            return
        self.lots.setdefault(ticker, []).append(Lot(ticker, asset_class, quantity, price, on_date))
        self.cash -= quantity * price

    def sell(
        self,
        ticker: str,
        quantity: float,
        price: float,
        on_date: date,
        tracker: TaxYearTracker,
        policy: str,
        apply_tax: bool = True,
    ) -> list[Disposal]:
        available = self.lots.get(ticker, [])
        if not available or quantity <= 0:
            return []

        selector = LOT_SELECTORS[policy]
        chosen = selector(available, quantity, price, on_date)

        disposals: list[Disposal] = []
        for lot, take in chosen:
            gross_gain = (price - lot.cost_basis_price) * take
            if apply_tax:
                result = tracker.record_disposal(lot.asset_class, lot.acquired_on, on_date, gross_gain)
                tax_owed = result.tax_owed
            else:
                tax_owed = 0.0
            proceeds = take * price
            self.cash += proceeds - tax_owed
            disposals.append(Disposal(ticker, take, proceeds, gross_gain, tax_owed))
            lot.quantity -= take

        self.lots[ticker] = [lot for lot in available if lot.quantity > MIN_LOT_QUANTITY]
        return disposals


def rebalance_to_target(
    ledger: PortfolioLedger,
    target_weights: dict[str, float],
    asset_classes: dict[str, str],
    prices: dict[str, float],
    on_date: date,
    tracker: TaxYearTracker,
    policy: str,
    apply_tax: bool = True,
) -> list[Disposal]:
    """Trade `ledger` from its current holdings toward `target_weights`,
    selling via `policy` ("fifo" or "tax_aware") and buying new lots at
    today's price. Sells execute before buys so sale proceeds (net of tax)
    fund the purchases, same as a real rebalance."""
    total_value = ledger.holdings_value(prices)
    if total_value <= 0:
        return []

    current_quantities = {ticker: sum(lot.quantity for lot in lots) for ticker, lots in ledger.lots.items()}
    all_tickers = set(current_quantities) | set(target_weights)

    sell_orders: list[tuple[str, float]] = []
    buy_orders: list[tuple[str, float]] = []
    for ticker in all_tickers:
        price = prices.get(ticker)
        if price is None or price <= 0:
            continue
        target_value = target_weights.get(ticker, 0.0) * total_value
        current_value = current_quantities.get(ticker, 0.0) * price
        delta_value = target_value - current_value
        if delta_value < -MIN_TRADE_VALUE:
            sell_orders.append((ticker, -delta_value / price))
        elif delta_value > MIN_TRADE_VALUE:
            buy_orders.append((ticker, delta_value / price))

    all_disposals: list[Disposal] = []
    for ticker, quantity in sell_orders:
        all_disposals.extend(ledger.sell(ticker, quantity, prices[ticker], on_date, tracker, policy, apply_tax))

    for ticker, quantity in buy_orders:
        ledger.buy(ticker, asset_classes.get(ticker, "stock"), quantity, prices[ticker], on_date)

    return all_disposals
