"""
seed_demo_portfolio.py
======================
Creates a demo user and an INR 80,000 demo portfolio seeded across 5 asset
classes, with avg_buy_price set to real historical closes from ~12 months ago.

Run from repo root:
    python -m backend.scripts.seed_demo_portfolio

Or directly:
    python backend/scripts/seed_demo_portfolio.py
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from pathlib import Path

# ---------------------------------------------------------------------------
# Path bootstrap - works whether backend/ is in PYTHONPATH or not
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent          # backend/scripts/
_BACKEND_DIR = _SCRIPT_DIR.parent                       # backend/
_REPO_ROOT = _BACKEND_DIR.parent                        # d:/QuantPortfolio/

for _p in [str(_REPO_ROOT), str(_BACKEND_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Load .env before importing settings
from dotenv import load_dotenv
load_dotenv(_BACKEND_DIR / ".env", override=False)

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
import yfinance as yf
from passlib.context import CryptContext
from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.config import get_settings
from backend.database import build_sqlite_database_url
from backend.models import assets, holdings, portfolios, users

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# ---------------------------------------------------------------------------
# Demo configuration
# ---------------------------------------------------------------------------
DEMO_EMAIL = "demo@quantportfolio.in"
DEMO_PASSWORD = "Demo@1234"
DEMO_FULL_NAME = "Demo Investor"

PORTFOLIO_NAME = "Demo Portfolio"
PORTFOLIO_DESC = "Seeded demo portfolio for invigilator demo"
BASE_CURRENCY = "INR"

TOTAL_INR = 80_000.0

# Portfolio constraints
DEMO_CONSTRAINTS = {
    "stocks": {"min": 0.10, "max": 0.50},
    "crypto": {"min": 0.05, "max": 0.20},
    "gold":   {"min": 0.05, "max": 0.20},
    "bonds":  {"min": 0.10, "max": 0.30},
    "mf_etf": {"min": 0.05, "max": 0.30},
}

# Holdings: (ticker, asset_class, exchange, currency, data_source, inr_allocation, pct)
HOLDINGS_CONFIG = [
    ("RELIANCE.NS",  "stock",  "NSE",    "INR", "yahoo",     16_000.0, 20),
    ("BTC-USD",      "crypto", "CRYPTO", "USD", "coingecko",  8_000.0, 10),
    ("GLD",          "mf_etf", "NYSE",   "USD", "yahoo",      8_000.0, 10),
    ("GOLDBEES.NS",  "gold",   "NSE",    "INR", "yahoo",      8_000.0, 10),
    ("NIFTYBEES.NS", "mf_etf", "NSE",    "INR", "yahoo",     16_000.0, 20),
    ("HDFCBANK.NS",  "stock",  "NSE",    "INR", "yahoo",      8_000.0, 10),
    ("LTGILTDIR.NS", "bond",   "NSE",    "INR", "yahoo",      8_000.0, 10),
    ("TCS.NS",       "stock",  "NSE",    "INR", "yahoo",      8_000.0, 10),
]

# ---------------------------------------------------------------------------
# Price helpers
# ---------------------------------------------------------------------------

def _fetch_usd_to_inr() -> float:
    """Fetch current USD/INR exchange rate via yfinance."""
    try:
        ticker = yf.Ticker("USDINR=X")
        hist = ticker.history(period="2d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    return 84.0  # fallback


def _fetch_historical_and_current(ticker: str, currency: str, usd_inr: float) -> tuple[float, float]:
    """
    Returns (hist_price_inr, current_price_inr).
    hist_price is the close ~252 trading days ago (13-month window).
    Current is the most recent close.
    Both are expressed in INR.
    """
    df = yf.download(ticker, period="13mo", auto_adjust=True, progress=False)
    if df.empty:
        raise ValueError(f"No data for {ticker}")

    close = df["Close"]
    # Drop NaN rows
    close = close.dropna()

    n = len(close)
    # Index ~252 trading days from the end (or as far back as possible)
    hist_idx = max(0, n - 252)
    hist_price_raw = float(close.iloc[hist_idx])
    current_price_raw = float(close.iloc[-1])

    # Convert USD assets to INR
    if currency == "USD":
        return hist_price_raw * usd_inr, current_price_raw * usd_inr

    return hist_price_raw, current_price_raw


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def _build_engine(db_url: str):
    """Build an async engine, falling back to SQLite if Postgres unavailable."""
    kwargs: dict = {"pool_pre_ping": True}
    if db_url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_async_engine(db_url, **kwargs)


async def _get_or_create_db_url() -> str:
    """Return the DATABASE_URL from settings, with SQLite fallback."""
    db_url = settings.DATABASE_URL
    # Prefer SQLite for local seeding if Postgres is not configured
    if "localhost" in db_url or "127.0.0.1" in db_url:
        # Try to use SQLite as it is always available locally
        sqlite_url = build_sqlite_database_url()
        return sqlite_url
    return db_url


async def _ensure_asset(session: AsyncSession, ticker: str, asset_class: str,
                        exchange: str, currency: str, data_source: str) -> None:
    """Insert asset row if it does not already exist."""
    result = await session.execute(select(assets).where(assets.c.ticker == ticker))
    if result.first() is not None:
        return
    await session.execute(
        insert(assets).values(
            ticker=ticker,
            name=ticker,
            asset_class=asset_class,
            exchange=exchange,
            currency=currency,
            data_source=data_source,
            is_active=True,
        )
    )


async def _get_or_create_user(session: AsyncSession) -> uuid.UUID:
    """Return existing demo user id or create a new one."""
    result = await session.execute(select(users).where(users.c.email == DEMO_EMAIL))
    row = result.first()
    if row is not None:
        print(f"  Demo user already exists (id={row.id}) - skipping user creation.")
        return row.id

    user_id = uuid.uuid4()
    hashed = pwd_context.hash(DEMO_PASSWORD)
    await session.execute(
        insert(users).values(
            id=user_id,
            email=DEMO_EMAIL,
            hashed_password=hashed,
            full_name=DEMO_FULL_NAME,
            is_active=True,
        )
    )
    print(f"  Created demo user (id={user_id})")
    return user_id


async def _get_or_create_portfolio(session: AsyncSession, user_id: uuid.UUID) -> uuid.UUID:
    """Return existing demo portfolio id or create a new one."""
    result = await session.execute(
        select(portfolios).where(
            portfolios.c.user_id == user_id,
            portfolios.c.name == PORTFOLIO_NAME,
        )
    )
    row = result.first()
    if row is not None:
        print(f"  Portfolio already exists (id={row.id}) - skipping portfolio creation.")
        return row.id

    portfolio_id = uuid.uuid4()
    await session.execute(
        insert(portfolios).values(
            id=portfolio_id,
            user_id=user_id,
            name=PORTFOLIO_NAME,
            description=PORTFOLIO_DESC,
            base_currency=BASE_CURRENCY,
            constraints=DEMO_CONSTRAINTS,
        )
    )
    print(f"  Created demo portfolio (id={portfolio_id})")
    return portfolio_id


async def _portfolio_has_holdings(session: AsyncSession, portfolio_id: uuid.UUID) -> bool:
    result = await session.execute(
        select(holdings).where(holdings.c.portfolio_id == portfolio_id)
    )
    return result.first() is not None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

async def main() -> None:
    print("\n=== QuantPortfolio Demo Seed Script ===\n")

    # 1. Fetch USD/INR rate
    print("Fetching USD/INR exchange rate...")
    usd_inr = _fetch_usd_to_inr()
    print(f"  USD/INR = {usd_inr:.2f}\n")

    # 2. Fetch price data for all holdings
    print("Fetching price data (13-month window)...")
    price_data: list[tuple[str, str, float, float, float, float, int]] = []
    # (ticker, currency, hist_price_inr, current_price_inr, inr_alloc, qty, pct)

    for ticker, asset_class, exchange, currency, data_source, inr_alloc, pct in HOLDINGS_CONFIG:
        try:
            hist_price, current_price = _fetch_historical_and_current(ticker, currency, usd_inr)
            qty = inr_alloc / hist_price
            pnl_pct = ((current_price - hist_price) / hist_price) * 100
            price_data.append((ticker, currency, hist_price, current_price, inr_alloc, qty, pct, asset_class, exchange, data_source, pnl_pct))
            print(f"  {ticker:16s}  hist={hist_price:10.2f} INR  current={current_price:10.2f} INR  qty={qty:.4f}  pnl={pnl_pct:+.1f}%")
        except Exception as exc:
            print(f"  WARNING: {ticker} - could not fetch data: {exc}")
            # Use a fallback placeholder
            price_data.append((ticker, currency, 1.0, 1.0, inr_alloc, inr_alloc, pct, asset_class, exchange, data_source, 0.0))

    # 3. Connect to DB and seed
    print("\nConnecting to database...")
    db_url = await _get_or_create_db_url()

    # Mask credentials in output
    _display_url = db_url.split("@")[-1] if "@" in db_url else db_url
    print(f"  DB: ...@{_display_url}\n")

    engine = _build_engine(db_url)

    # Import all models to register tables with metadata
    from backend.models import asset  # noqa: F401 - registers assets table
    from backend.models import holding  # noqa: F401
    from backend.models import portfolio  # noqa: F401
    from backend.models import user  # noqa: F401
    from backend.database import metadata

    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)

    async_session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with async_session() as session:
        async with session.begin():
            # Create user
            print("Creating demo user...")
            user_id = await _get_or_create_user(session)

            # Create portfolio
            print("Creating demo portfolio...")
            portfolio_id = await _get_or_create_portfolio(session, user_id)

            # Seed assets and holdings
            if await _portfolio_has_holdings(session, portfolio_id):
                print("  Holdings already exist - skipping holdings creation.")
            else:
                print("Seeding assets and holdings...")
                for row in price_data:
                    ticker, currency, hist_price, current_price, inr_alloc, qty, pct, asset_class, exchange, data_source, pnl_pct = row

                    # Ensure asset exists
                    await _ensure_asset(session, ticker, asset_class, exchange, currency, data_source)

                    # Insert holding
                    await session.execute(
                        insert(holdings).values(
                            id=uuid.uuid4(),
                            portfolio_id=portfolio_id,
                            ticker=ticker,
                            quantity=qty,
                            avg_buy_price=hist_price,
                            buy_currency="INR",
                        )
                    )
                    print(f"  Inserted holding: {ticker} qty={qty:.4f} avg_buy={hist_price:.2f}")

    await engine.dispose()

    # 4. Summary table
    print("\n=== Seed Summary ===")
    print(f"{'Ticker':16s} {'Alloc%':>7s} {'Qty':>10s} {'AvgBuy(INR)':>14s} {'Current(INR)':>14s} {'PnL%':>8s}")
    print("-" * 75)
    for row in price_data:
        ticker, currency, hist_price, current_price, inr_alloc, qty, pct, asset_class, exchange, data_source, pnl_pct = row
        print(f"{ticker:16s} {pct:>6d}%  {qty:>10.4f} {hist_price:>14.2f} {current_price:>14.2f} {pnl_pct:>+7.1f}%")

    print(f"\n  Total INR allocated: {TOTAL_INR:,.0f}")
    print("\n=== Demo Credentials ===")
    print(f"  Email   : {DEMO_EMAIL}")
    print("  Password: (see DEMO_PASSWORD in script - not printed for security)")
    print("\nSeed complete.\n")


if __name__ == "__main__":
    asyncio.run(main())
