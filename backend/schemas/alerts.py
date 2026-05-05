from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AlertPortfolio(BaseModel):
    id: uuid.UUID
    name: str


class AlertOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    portfolio_id: uuid.UUID
    alert_type: str
    message: str
    created_at: datetime
    is_read: bool
    portfolio: AlertPortfolio | None = None