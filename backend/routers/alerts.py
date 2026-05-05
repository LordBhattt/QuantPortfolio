from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from backend.data_types import CurrentUser
from backend.database import get_db
from backend.dependencies import get_current_user
from backend.schemas.alerts import AlertOut
from backend.services.alerts_service import list_unread_alerts, mark_alert_read, mark_all_alerts_read


router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


@router.get("/", response_model=list[AlertOut])
async def get_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> list[AlertOut]:
    return await list_unread_alerts(current_user.id, db)


@router.patch("/{alert_id}/read", status_code=204)
async def read_alert(
    alert_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    await mark_alert_read(alert_id, current_user.id, db)
    return Response(status_code=204)


@router.patch("/read-all", status_code=204)
async def read_all_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> Response:
    await mark_all_alerts_read(current_user.id, db)
    return Response(status_code=204)