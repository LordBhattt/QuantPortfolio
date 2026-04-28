"""initial schema

Revision ID: 20260428_0001
Revises:
Create Date: 2026-04-28 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260428_0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    asset_class_enum = sa.Enum("stock", "crypto", "gold", "mf_etf", "bond", name="asset_class_enum")

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)

    op.create_table(
        "assets",
        sa.Column("ticker", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("asset_class", asset_class_enum, nullable=False),
        sa.Column("exchange", sa.String(length=64), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("data_source", sa.String(length=32), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("ticker", name=op.f("pk_assets")),
    )
    op.create_index(op.f("ix_assets_asset_class"), "assets", ["asset_class"], unique=False)

    op.create_table(
        "portfolios",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("base_currency", sa.String(length=3), nullable=False, server_default="INR"),
        sa.Column("constraints", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_portfolios_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_portfolios")),
    )
    op.create_index(op.f("ix_portfolios_user_id"), "portfolios", ["user_id"], unique=False)

    op.create_table(
        "holdings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("portfolio_id", sa.Uuid(), nullable=False),
        sa.Column("ticker", sa.String(length=64), nullable=False),
        sa.Column("quantity", sa.Float(), nullable=False),
        sa.Column("avg_buy_price", sa.Float(), nullable=False),
        sa.Column("buy_currency", sa.String(length=3), nullable=False, server_default="USD"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["portfolio_id"],
            ["portfolios.id"],
            name=op.f("fk_holdings_portfolio_id_portfolios"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["ticker"], ["assets.ticker"], name=op.f("fk_holdings_ticker_assets")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_holdings")),
    )
    op.create_index(op.f("ix_holdings_portfolio_id"), "holdings", ["portfolio_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_holdings_portfolio_id"), table_name="holdings")
    op.drop_table("holdings")
    op.drop_index(op.f("ix_portfolios_user_id"), table_name="portfolios")
    op.drop_table("portfolios")
    op.drop_index(op.f("ix_assets_asset_class"), table_name="assets")
    op.drop_table("assets")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")
    sa.Enum("stock", "crypto", "gold", "mf_etf", "bond", name="asset_class_enum").drop(op.get_bind(), checkfirst=True)
