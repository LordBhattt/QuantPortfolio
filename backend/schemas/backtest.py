from typing import Literal, Optional

from pydantic import BaseModel, Field


class BacktestRequest(BaseModel):
    portfolio_id: str
    lookback_years: int = Field(default=3, ge=1, le=5)
    rebalance: Literal["weekly", "monthly", "quarterly"] = Field(default="monthly")
    risk_tolerance: float = Field(default=0.5, ge=0.0, le=1.0)
    cost_bps: int = Field(default=10, ge=0, le=200)
    use_ml: bool = Field(default=False)
    use_regime: bool = Field(default=False)


class StrategyMetrics(BaseModel):
    name: str
    final_value: float
    total_profit_inr: float
    cagr: float
    volatility: float
    sharpe: float
    sortino: float
    max_drawdown: float
    calmar: float
    avg_turnover: float


class BacktestResponse(BaseModel):
    strategies: list[StrategyMetrics]
    equity_curves: dict  # {strategy_name: [{date, value}, ...]}
    drawdown_curves: dict  # {strategy_name: [{date, drawdown}, ...]}
    weights_history: list  # [{date, ticker: weight, ...}] for Optimized strategy only
    best_strategy: str
    headline: str  # "Optimized vs Equal Weight over 3Y: +INR X"
    parameters: dict
    selected_settings: dict = Field(default_factory=dict)
