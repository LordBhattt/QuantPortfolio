"""add investor profiles

Revision ID: 20260505_0001
Revises: 20260428_0001
Create Date: 2026-05-05 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260505_0001"
down_revision: Union[str, None] = "20260428_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "investor_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("investment_amount", sa.Float(), nullable=False),
        sa.Column("investment_horizon", sa.String(length=32), nullable=False),
        sa.Column("risk_appetite", sa.String(length=32), nullable=False),
        sa.Column("income_stability", sa.String(length=16), nullable=False),
        sa.Column("existing_investments", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("age_group", sa.String(length=16), nullable=False),
        sa.Column("risk_score", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_investor_profiles_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_investor_profiles")),
        sa.UniqueConstraint("user_id", name=op.f("uq_investor_profiles_user_id")),
        sa.CheckConstraint("risk_score >= 1 AND risk_score <= 10", name=op.f("ck_investor_profiles_risk_score_range")),
    )
    op.create_index(op.f("ix_investor_profiles_user_id"), "investor_profiles", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_investor_profiles_user_id"), table_name="investor_profiles")
    op.drop_table("investor_profiles")