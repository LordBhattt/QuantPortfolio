from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.errors import AppError
from backend.models.portfolio import portfolios
from backend.models.portfolio_alert import portfolio_alerts
from backend.schemas.alerts import AlertOut, AlertPortfolio


async def list_unread_alerts(user_id: UUID, db: AsyncSession) -> list[AlertOut]:
    result = await db.execute(
        select(
            portfolio_alerts.c.id,
            portfolio_alerts.c.portfolio_id,
            portfolio_alerts.c.alert_type,
            portfolio_alerts.c.message,
            portfolio_alerts.c.created_at,
            portfolio_alerts.c.is_read,
            portfolios.c.name.label("portfolio_name"),
        )
        .select_from(portfolio_alerts.join(portfolios, portfolio_alerts.c.portfolio_id == portfolios.c.id))
        .where(portfolios.c.user_id == user_id, portfolio_alerts.c.is_read.is_(False))
        .order_by(portfolio_alerts.c.created_at.desc())
    )
    return [_row_to_alert(row) for row in result.mappings().all()]


async def mark_alert_read(alert_id: UUID, user_id: UUID, db: AsyncSession) -> None:
    result = await db.execute(
        update(portfolio_alerts)
        .where(
            portfolio_alerts.c.id == alert_id,
            portfolio_alerts.c.portfolio_id.in_(select(portfolios.c.id).where(portfolios.c.user_id == user_id)),
        )
        .values(is_read=True)
        .returning(portfolio_alerts.c.id)
    )
    if result.scalar_one_or_none() is None:
        raise AppError("Alert not found", "alert_not_found", "Alert not found", 404)


async def mark_all_alerts_read(user_id: UUID, db: AsyncSession) -> int:
    result = await db.execute(
        update(portfolio_alerts)
        .where(
            portfolio_alerts.c.portfolio_id.in_(select(portfolios.c.id).where(portfolios.c.user_id == user_id)),
            portfolio_alerts.c.is_read.is_(False),
        )
        .values(is_read=True)
    )
    return int(result.rowcount or 0)


def _row_to_alert(row: dict) -> AlertOut:
    portfolio = AlertPortfolio(id=row["portfolio_id"], name=row["portfolio_name"])
    return AlertOut.model_validate(
        {
            "id": row["id"],
            "portfolio_id": row["portfolio_id"],
            "alert_type": row["alert_type"],
            "message": row["message"],
            "created_at": row["created_at"],
            "is_read": row["is_read"],
            "portfolio": portfolio,
        }
    )