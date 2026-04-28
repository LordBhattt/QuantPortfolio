import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from backend.schemas.optimization import PortfolioConstraints


BaseCurrency = Literal["INR", "USD"]


class PortfolioCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    base_currency: BaseCurrency = "INR"
    constraints: PortfolioConstraints | None = None


class PortfolioUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=500)
    base_currency: BaseCurrency | None = None
    constraints: PortfolioConstraints | None = None


class PortfolioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    description: str | None = None
    base_currency: BaseCurrency
    constraints: dict
    created_at: datetime | None = None
    updated_at: datetime | None = None


class HoldingCreate(BaseModel):
    ticker: str
    quantity: float = Field(gt=0)
    avg_buy_price: float = Field(gt=0)
    buy_currency: str = "USD"

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("buy_currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()


class HoldingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    portfolio_id: uuid.UUID
    ticker: str
    quantity: float
    avg_buy_price: float
    buy_currency: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
