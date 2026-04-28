import uuid

from sqlalchemy import JSON, Column, DateTime, ForeignKey, String, func
from sqlalchemy import Uuid

from backend.database import metadata


def default_constraints() -> dict[str, dict[str, float]]:
    return {
        "stocks": {"min": 0.0, "max": 1.0},
        "crypto": {"min": 0.0, "max": 1.0},
        "gold": {"min": 0.0, "max": 1.0},
        "mf_etf": {"min": 0.0, "max": 1.0},
        "bonds": {"min": 0.0, "max": 1.0},
    }


portfolios = metadata.tables.get("portfolios")

if portfolios is None:
    from sqlalchemy import Table

    portfolios = Table(
        "portfolios",
        metadata,
        Column("id", Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4),
        Column("user_id", Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True),
        Column("name", String(255), nullable=False),
        Column("description", String(500), nullable=True),
        Column("base_currency", String(3), nullable=False, default="INR", server_default="INR"),
        Column("constraints", JSON, nullable=False, default=default_constraints),
        Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        Column("updated_at", DateTime(timezone=True), nullable=True, onupdate=func.now()),
    )
