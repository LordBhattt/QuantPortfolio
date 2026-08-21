from pydantic import BaseModel


class StrategyMetricsResponse(BaseModel):
    cagr: float
    annual_volatility: float
    sharpe: float
    sortino: float
    calmar: float
    max_drawdown: float
    var_95: float
    cvar_95: float
    avg_turnover: float
    n_periods: int
    n_observations: int


class RegimeBreakdownResponse(BaseModel):
    regime: str
    metrics: StrategyMetricsResponse


class EquityCurvePoint(BaseModel):
    date: str
    value: float
    regime: str | None = None


class StrategySeriesResponse(BaseModel):
    name: str
    equity_curve: list[EquityCurvePoint]
    metrics: StrategyMetricsResponse
    regime_breakdown: list[RegimeBreakdownResponse]


class SignificanceResponse(BaseModel):
    strategy: str
    observed_difference: float
    ci_lower: float
    ci_upper: float
    confidence: float
    significant: bool


class BanditPosteriorEntry(BaseModel):
    regime: str
    arm: str
    mean: float
    variance: float
    n: int


class BacktestResponse(BaseModel):
    universe: list[str]
    lookback_days: int
    transaction_cost_bps: float
    baseline: str
    data_through: str
    strategies: list[StrategySeriesResponse]
    significance_vs_baseline: list[SignificanceResponse]
    bandit_posterior: list[BanditPosteriorEntry]
