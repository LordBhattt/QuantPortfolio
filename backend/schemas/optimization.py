import uuid

from pydantic import BaseModel, Field, model_validator


class AssetClassConstraint(BaseModel):
    min: float = Field(ge=0.0, le=1.0)
    max: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_bounds(self) -> "AssetClassConstraint":
        if self.max < self.min:
            raise ValueError("max must be >= min")
        return self


class PortfolioConstraints(BaseModel):
    stocks: AssetClassConstraint = AssetClassConstraint(min=0.0, max=1.0)
    crypto: AssetClassConstraint = AssetClassConstraint(min=0.0, max=1.0)
    gold: AssetClassConstraint = AssetClassConstraint(min=0.0, max=1.0)
    mf_etf: AssetClassConstraint = AssetClassConstraint(min=0.0, max=1.0)
    bonds: AssetClassConstraint = AssetClassConstraint(min=0.0, max=1.0)

    @model_validator(mode="after")
    def feasibility_check(self) -> "PortfolioConstraints":
        min_sum = (
            self.stocks.min
            + self.crypto.min
            + self.gold.min
            + self.mf_etf.min
            + self.bonds.min
        )
        max_sum = (
            self.stocks.max
            + self.crypto.max
            + self.gold.max
            + self.mf_etf.max
            + self.bonds.max
        )
        if min_sum > 1.0:
            raise ValueError("sum of minimum constraints must be <= 1.0")
        if max_sum < 1.0:
            raise ValueError("sum of maximum constraints must be >= 1.0")
        return self


class UserView(BaseModel):
    ticker: str
    expected_return: float
    confidence: float = Field(ge=0.0, le=1.0, default=0.5)


class OptimizationRequest(BaseModel):
    portfolio_id: uuid.UUID
    risk_tolerance: float = Field(ge=0.0, le=1.0, description="0=min variance, 1=max return")
    constraints: PortfolioConstraints | None = None
    user_views: list[UserView] = Field(default_factory=list)
    use_regime_scaling: bool = True
    use_lstm_forecasts: bool = True


class AssetWeight(BaseModel):
    ticker: str
    asset_class: str
    weight: float
    current_value_usd: float
    target_value_usd: float
    trade_delta_usd: float


class FrontierPoint(BaseModel):
    expected_return: float
    volatility: float
    sharpe: float
    weights: dict[str, float]


class OptimizationResult(BaseModel):
    portfolio_id: uuid.UUID
    regime: str
    regime_probability: float
    usd_inr_rate: float
    optimal_weights: list[AssetWeight]
    portfolio_return: float
    portfolio_volatility: float
    sharpe_ratio: float
    efficient_frontier: list[FrontierPoint]
    rebalance_trades: list[AssetWeight]
