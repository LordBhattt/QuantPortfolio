import uuid

from sqlalchemy import Boolean, Column, DateTime, String, func
from sqlalchemy import Uuid

from backend.database import metadata

users = metadata.tables.get("users")

if users is None:
    from sqlalchemy import Table

    users = Table(
        "users",
        metadata,
        Column("id", Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4),
        Column("email", String(320), unique=True, nullable=False, index=True),
        Column("hashed_password", String(255), nullable=False),
        Column("full_name", String(255), nullable=True),
        Column("is_active", Boolean, nullable=False, default=True, server_default="true"),
        Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
        Column("updated_at", DateTime(timezone=True), nullable=True, onupdate=func.now()),
    )
