import uuid

from sqlalchemy import Float, JSON, Column, DateTime, ForeignKey, String, func
from sqlalchemy import Uuid

from backend.database import metadata


def default_constraints() -> dict[str, dict[str, float]]:
    return {
        "stocks": {"min": 0.0, "max": 0.55},
        "crypto": {"min": 0.0, "max": 0.15},
        "gold": {"min": 0.0, "max": 0.20},
        "mf_etf": {"min": 0.0, "max": 0.30},
        "bonds": {"min": 0.10, "max": 0.50},
    }


def constraints_for_risk_score(risk_score: int) -> dict[str, dict[str, float]]:
    """Return asset-class constraints calibrated to the investor's risk score (1-10)."""
    if risk_score <= 3:
        # Conservative
        return {
            "stocks": {"min": 0.05, "max": 0.35},
            "crypto": {"min": 0.0, "max": 0.05},
            "gold": {"min": 0.05, "max": 0.25},
            "mf_etf": {"min": 0.10, "max": 0.35},
            "bonds": {"min": 0.25, "max": 0.55},
        }
    if risk_score <= 6:
        # Moderate
        return {
            "stocks": {"min": 0.10, "max": 0.50},
            "crypto": {"min": 0.0, "max": 0.10},
            "gold": {"min": 0.05, "max": 0.20},
            "mf_etf": {"min": 0.05, "max": 0.30},
            "bonds": {"min": 0.10, "max": 0.40},
        }
    # Aggressive
    return {
        "stocks": {"min": 0.15, "max": 0.60},
        "crypto": {"min": 0.0, "max": 0.15},
        "gold": {"min": 0.0, "max": 0.15},
        "mf_etf": {"min": 0.05, "max": 0.25},
        "bonds": {"min": 0.05, "max": 0.30},
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
        Column("last_optimized_weights", JSON, nullable=True),
        Column("peak_value", Float, nullable=True),
        Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        Column("updated_at", DateTime(timezone=True), nullable=True, onupdate=func.now()),
    )
