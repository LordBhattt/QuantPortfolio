import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


InvestmentHorizon = Literal["short_term", "medium_term", "long_term"]
RiskAppetite = Literal["conservative", "moderate", "aggressive"]
IncomeStability = Literal["stable", "variable"]
AgeGroup = Literal["18-25", "26-35", "36-50", "50+"]


class InvestorProfileCreate(BaseModel):
    investment_amount: float = Field(gt=0)
    investment_horizon: InvestmentHorizon
    risk_appetite: RiskAppetite
    income_stability: IncomeStability
    existing_investments: bool
    age_group: AgeGroup


class InvestorProfileOut(InvestorProfileCreate):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    risk_score: int
    created_at: datetime | None = None
    updated_at: datetime | None = None


class PortfolioRecommendation(BaseModel):
    ticker: str
    asset_class: str
    recommended_weight: float
    recommended_amount_inr: float
    current_price_inr: float | None = None