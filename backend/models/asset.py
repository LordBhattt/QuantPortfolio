import enum

from sqlalchemy import Boolean, Column, Enum, String

from backend.database import metadata


class AssetClass(str, enum.Enum):
    STOCK = "stock"
    CRYPTO = "crypto"
    GOLD = "gold"
    MF_ETF = "mf_etf"
    BOND = "bond"


assets = metadata.tables.get("assets")

if assets is None:
    from sqlalchemy import Table

    assets = Table(
        "assets",
        metadata,
        Column("ticker", String(64), primary_key=True),
        Column("name", String(255), nullable=False),
        Column(
            "asset_class",
            Enum(
                AssetClass,
                name="asset_class_enum",
                values_callable=lambda enum_cls: [member.value for member in enum_cls],
            ),
            nullable=False,
            index=True,
        ),
        Column("exchange", String(64), nullable=True),
        Column("currency", String(3), nullable=False, default="USD", server_default="USD"),
        Column("data_source", String(32), nullable=False),
        Column("is_active", Boolean, nullable=False, default=True, server_default="true"),
    )
