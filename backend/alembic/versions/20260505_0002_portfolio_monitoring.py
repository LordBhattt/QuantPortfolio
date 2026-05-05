"""add portfolio monitoring columns and alerts

Revision ID: 20260505_0002
Revises: 20260505_0001
Create Date: 2026-05-05 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260505_0002"
down_revision: Union[str, None] = "20260505_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("portfolios", sa.Column("last_optimized_weights", sa.JSON(), nullable=True))
    op.add_column("portfolios", sa.Column("peak_value", sa.Float(), nullable=True))

    op.create_table(
        "portfolio_alerts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("alert_type", sa.String(length=64), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.ForeignKeyConstraint(["portfolio_id"], ["portfolios.id"], name=op.f("fk_portfolio_alerts_portfolio_id_portfolios"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_portfolio_alerts")),
    )
    op.create_index(op.f("ix_portfolio_alerts_portfolio_id"), "portfolio_alerts", ["portfolio_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_portfolio_alerts_portfolio_id"), table_name="portfolio_alerts")
    op.drop_table("portfolio_alerts")
    op.drop_column("portfolios", "peak_value")
    op.drop_column("portfolios", "last_optimized_weights")