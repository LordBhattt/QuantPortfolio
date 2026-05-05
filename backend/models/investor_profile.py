import uuid

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy import Uuid

from backend.database import metadata


investor_profiles = metadata.tables.get("investor_profiles")

if investor_profiles is None:
    from sqlalchemy import Table

    investor_profiles = Table(
        "investor_profiles",
        metadata,
        Column("id", Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4),
        Column("user_id", Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True, index=True),
        Column("investment_amount", Float, nullable=False),
        Column("investment_horizon", String(32), nullable=False),
        Column("risk_appetite", String(32), nullable=False),
        Column("income_stability", String(16), nullable=False),
        Column("existing_investments", Boolean, nullable=False, default=False, server_default="false"),
        Column("age_group", String(16), nullable=False),
        Column("risk_score", Integer, nullable=False),
        Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        Column("updated_at", DateTime(timezone=True), nullable=True, onupdate=func.now()),
    )

InvestorProfile = investor_profiles