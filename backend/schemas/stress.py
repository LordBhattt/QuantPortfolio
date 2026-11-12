from pydantic import BaseModel
from typing import Optional, List


class HoldingImpactOut(BaseModel):
    ticker: str
    asset_class: str
    weight: float
    scenario_return_pct: float
    portfolio_contribution_pct: float
    is_proxy: bool
    proxy_ticker: Optional[str]


class ScenarioResultOut(BaseModel):
    scenario_name: str
    scenario_label: str
    scenario_start: str
    scenario_end: str
    portfolio_return_pct: float
    portfolio_inr_impact: float
    per_holding: List[HoldingImpactOut]


class CustomShockRequest(BaseModel):
    equities_pct: float = 0.0
    crypto_pct: float = 0.0
    gold_pct: float = 0.0
    bonds_pct: float = 0.0
    inr_move_pct: float = 0.0


class StressTestResponse(BaseModel):
    portfolio_value_inr: float
    historical_scenarios: List[ScenarioResultOut]
    custom_shock: Optional[dict] = None
