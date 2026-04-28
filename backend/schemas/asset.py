from pydantic import BaseModel, ConfigDict, field_validator

from backend.models.asset import AssetClass


class AssetBase(BaseModel):
    name: str
    asset_class: AssetClass
    exchange: str | None = None
    currency: str = "USD"
    data_source: str
    is_active: bool = True

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str) -> str:
        return value.upper()

    @field_validator("data_source")
    @classmethod
    def validate_source(cls, value: str) -> str:
        normalized = value.strip().lower()
        allowed = {"yahoo", "coingecko", "amfi"}
        if normalized not in allowed:
            raise ValueError(f"data_source must be one of {sorted(allowed)}")
        return normalized


class AssetCreate(AssetBase):
    ticker: str

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        return value.strip().upper()


class AssetUpdate(BaseModel):
    name: str | None = None
    asset_class: AssetClass | None = None
    exchange: str | None = None
    currency: str | None = None
    data_source: str | None = None
    is_active: bool | None = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, value: str | None) -> str | None:
        return value.upper() if value is not None else value

    @field_validator("data_source")
    @classmethod
    def validate_source(cls, value: str | None) -> str | None:
        if value is None:
            return value
        normalized = value.strip().lower()
        allowed = {"yahoo", "coingecko", "amfi"}
        if normalized not in allowed:
            raise ValueError(f"data_source must be one of {sorted(allowed)}")
        return normalized


class AssetOut(AssetCreate):
    model_config = ConfigDict(from_attributes=True)

    name: str
    asset_class: AssetClass
    exchange: str | None = None
    currency: str
    data_source: str
    is_active: bool
