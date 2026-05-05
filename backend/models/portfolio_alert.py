import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, String, Text, func
from sqlalchemy import Uuid

from backend.database import metadata


portfolio_alerts = metadata.tables.get("portfolio_alerts")

if portfolio_alerts is None:
    from sqlalchemy import Table

    portfolio_alerts = Table(
        "portfolio_alerts",
        metadata,
        Column("id", Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4),
        Column("portfolio_id", Uuid(as_uuid=True), ForeignKey("portfolios.id", ondelete="CASCADE"), nullable=False, index=True),
        Column("alert_type", String(64), nullable=False),
        Column("message", Text, nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        Column("is_read", Boolean, nullable=False, default=False, server_default="false"),
    )

PortfolioAlert = portfolio_alerts