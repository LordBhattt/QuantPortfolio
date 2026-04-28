import uuid

from pydantic import BaseModel


class RiskMetrics(BaseModel):
    portfolio_id: uuid.UUID
    usd_inr_rate: float
    var_95: float
    var_99: float
    cvar_95: float
    cvar_99: float
    max_drawdown: float
    sharpe_ratio: float
    sortino_ratio: float
    calmar_ratio: float
    annualised_return: float
    annualised_volatility: float
    beta: float
    correlation_matrix: dict[str, dict[str, float]]


class MonteCarloResult(BaseModel):
    portfolio_id: uuid.UUID
    usd_inr_rate: float
    horizon_days: int
    paths: int
    percentiles: dict[str, list[float]]
    prob_loss: float
    expected_terminal_value: float
    initial_value: float
