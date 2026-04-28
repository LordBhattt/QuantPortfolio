import uuid

from sqlalchemy import Column, DateTime, Float, ForeignKey, String, func
from sqlalchemy import Uuid

from backend.database import metadata

holdings = metadata.tables.get("holdings")

if holdings is None:
    from sqlalchemy import Table

    holdings = Table(
        "holdings",
        metadata,
        Column("id", Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4),
        Column("portfolio_id", Uuid(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True),
        Column("ticker", String(64), ForeignKey("assets.ticker"), nullable=False),
        Column("quantity", Float, nullable=False),
        Column("avg_buy_price", Float, nullable=False),
        Column("buy_currency", String(3), nullable=False, default="USD", server_default="USD"),
        Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        Column("updated_at", DateTime(timezone=True), nullable=True, onupdate=func.now()),
    )
