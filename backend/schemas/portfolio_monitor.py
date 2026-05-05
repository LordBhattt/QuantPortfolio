from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DriftedAsset(BaseModel):
    ticker: str
    asset_class: str
    current_weight: float
    target_weight: float
    drift: float


class RebalanceAlert(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    portfolio_id: uuid.UUID
    triggered_at: datetime
    drifted_assets: list[DriftedAsset] = Field(default_factory=list)
    recommended_action: Literal["rebalance"] = "rebalance"
    current_value_inr: float
    peak_value_inr: float | None = None
    peak_drop_pct: float | None = None
    message: str