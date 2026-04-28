import uuid

from pydantic import BaseModel, Field


class PerformancePoint(BaseModel):
    date: str
    portfolio: float
    benchmark: float


class FactorExposure(BaseModel):
    portfolio_id: uuid.UUID
    alpha: float
    beta_market: float
    beta_smb: float
    beta_hml: float
    beta_rmw: float
    beta_cma: float
    r_squared: float
    residual_std: float


class PerformanceAttribution(BaseModel):
    ticker: str
    name: str | None = None
    asset_class: str
    weight: float
    quantity: float | None = None
    avg_buy_price_inr: float | None = None
    current_price_inr: float | None = None
    current_value_inr: float | None = None
    pnl_inr: float | None = None
    pnl_pct: float | None = None
    sparkline_inr: list[float] = Field(default_factory=list)
    contribution_to_return: float
    contribution_to_risk: float


class PortfolioAnalytics(BaseModel):
    portfolio_id: uuid.UUID
    usd_inr_rate: float
    total_value_usd: float
    total_value_inr: float
    day_pnl_usd: float
    day_pnl_inr: float
    day_pnl_pct: float
    total_pnl_usd: float
    total_pnl_inr: float
    total_pnl_pct: float
    performance_series: list[PerformancePoint] = Field(default_factory=list)
    asset_class_allocation: dict[str, float]
    holdings_breakdown: list[PerformanceAttribution]
    factor_exposure: FactorExposure
