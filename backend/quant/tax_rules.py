"""Indian capital gains tax rules for equities, mutual funds/ETFs, gold,
bonds/debt funds, and crypto (Virtual Digital Assets).

Rates reflect Union Budget 2024 (post 23 July 2024) law:
  - Equity / equity-oriented MF-ETF: STCG 20% (<12mo), LTCG 12.5% (>=12mo)
    on aggregate gains above Rs 1.25L per fiscal year (Sec 112A).
  - Gold: STCG at the investor's slab rate (<24mo), LTCG 12.5% (>=24mo).
  - Bonds / debt-oriented funds: always taxed at the slab rate, regardless
    of holding period -- debt funds lost LTCG eligibility entirely under
    the FY2023-24 reclassification and Budget 2024 did not restore it.
  - Crypto (VDAs, Sec 115BBH): flat 30% on gains with NO holding-period
    distinction, and losses can offset NOTHING -- not other income, not
    other crypto disposals, and cannot be carried forward. This is the
    structurally distinctive rule this module exists to model correctly.

These are illustrative/representative rates for measuring the STRUCTURAL
effect of holding-period- and asset-class-dependent taxation on
rebalancing decisions. They are not a substitute for professional tax
advice: real liability also depends on the investor's total income slab,
surcharge, cess, Section 87A rebate, and Indian tax law is revised most
fiscal years. DEFAULT_SLAB_RATE below is a single representative
assumption standing in for a genuinely progressive, investor-specific
slab rate.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

EQUITY_LTCG_EXEMPTION_PER_FY = 125_000.0  # Sec 112A, aggregate across equity/equity-MF LTCG per fiscal year
DEFAULT_SLAB_RATE = 0.30  # representative top-slab assumption
CRYPTO_FLAT_RATE = 0.30

LONG_TERM_THRESHOLD_DAYS: dict[str, int | None] = {
    "stock": 365,
    "mf_etf": 365,
    "gold": 730,
    "bond": None,  # debt/bond funds never qualify for LTCG treatment
    "crypto": None,  # not applicable -- flat rate regardless of holding period
}

SHORT_TERM_RATES: dict[str, float] = {
    "stock": 0.20,
    "mf_etf": 0.20,
    "gold": DEFAULT_SLAB_RATE,
    "bond": DEFAULT_SLAB_RATE,
}

LONG_TERM_RATES: dict[str, float] = {
    "stock": 0.125,
    "mf_etf": 0.125,
    "gold": 0.125,
    "bond": DEFAULT_SLAB_RATE,
}

EQUITY_LIKE_CLASSES = {"stock", "mf_etf"}


def holding_period_days(acquired_on: date, sold_on: date) -> int:
    return (sold_on - acquired_on).days


def is_long_term(asset_class: str, holding_days: int) -> bool:
    threshold = LONG_TERM_THRESHOLD_DAYS.get(asset_class)
    if threshold is None:
        return False
    return holding_days >= threshold


def fiscal_year_start(on_date: date) -> date:
    """Indian fiscal year runs 1 April - 31 March."""
    if on_date.month >= 4:
        return date(on_date.year, 4, 1)
    return date(on_date.year - 1, 4, 1)


@dataclass
class DisposalResult:
    asset_class: str
    is_long_term: bool
    gross_gain: float  # can be negative (a loss); for crypto, a loss disposal has tax_owed == 0
    taxable_gain: float
    tax_rate: float
    tax_owed: float


class TaxYearTracker:
    """Tracks state that Indian capital gains rules require across disposals
    within a fiscal year: the Sec 112A Rs 1.25L equity/MF LTCG exemption
    (an annual aggregate, not a per-trade allowance) and unused short-/
    long-term capital losses available to offset later equity/gold/bond
    gains in the same year (STCL offsets STCG or LTCG; LTCL offsets only
    LTCG -- the standard set-off ordering). Crypto disposals never touch
    this tracker's loss pools at all: Sec 115BBH keeps every VDA disposal
    fully siloed from every other gain or loss, crypto included.
    """

    def __init__(self) -> None:
        self._fy_start: date | None = None
        self._equity_ltcg_realized = 0.0
        self._carried_stcl = 0.0
        self._carried_ltcl = 0.0

    def _roll_to_fiscal_year(self, on_date: date) -> None:
        fy = fiscal_year_start(on_date)
        if self._fy_start != fy:
            self._fy_start = fy
            self._equity_ltcg_realized = 0.0
            self._carried_stcl = 0.0
            self._carried_ltcl = 0.0

    def record_disposal(
        self,
        asset_class: str,
        acquired_on: date,
        sold_on: date,
        gross_gain: float,
    ) -> DisposalResult:
        self._roll_to_fiscal_year(sold_on)

        if asset_class == "crypto":
            taxable = max(gross_gain, 0.0)
            tax = taxable * CRYPTO_FLAT_RATE
            return DisposalResult("crypto", False, gross_gain, taxable, CRYPTO_FLAT_RATE, tax)

        holding_days = holding_period_days(acquired_on, sold_on)
        long_term = is_long_term(asset_class, holding_days)
        rate = (LONG_TERM_RATES if long_term else SHORT_TERM_RATES).get(asset_class, DEFAULT_SLAB_RATE)

        if gross_gain < 0:
            loss = -gross_gain
            if long_term:
                self._carried_ltcl += loss
            else:
                self._carried_stcl += loss
            return DisposalResult(asset_class, long_term, gross_gain, 0.0, rate, 0.0)

        gain = gross_gain
        if long_term:
            offset = min(self._carried_ltcl, gain)
            self._carried_ltcl -= offset
            gain -= offset
            offset = min(self._carried_stcl, gain)
            self._carried_stcl -= offset
            gain -= offset
        else:
            offset = min(self._carried_stcl, gain)
            self._carried_stcl -= offset
            gain -= offset

        taxable = gain
        if long_term and asset_class in EQUITY_LIKE_CLASSES:
            available_exemption = max(EQUITY_LTCG_EXEMPTION_PER_FY - self._equity_ltcg_realized, 0.0)
            exempt = min(available_exemption, taxable)
            self._equity_ltcg_realized += taxable
            taxable -= exempt

        tax = taxable * rate
        return DisposalResult(asset_class, long_term, gross_gain, taxable, rate, tax)
