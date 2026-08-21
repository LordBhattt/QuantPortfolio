"""Constrained mean-variance optimization."""

from typing import Optional

import cvxpy as cp
import numpy as np

from backend.schemas.optimization import FrontierPoint, PortfolioConstraints

_CLASS_ALIASES = {
    "stocks": "stock",
    "crypto": "crypto",
    "gold": "gold",
    "mf_etf": "mf_etf",
    "bonds": "bond",
}


def constrained_mvo(
    mu: np.ndarray,
    cov: np.ndarray,
    tickers: list[str],
    asset_classes: list[str],
    constraints: Optional[PortfolioConstraints],
    risk_tolerance: float,
    risk_free_rate: float = 0.065,
    max_single_asset_weight: float = 0.25,
) -> dict[str, float]:
    del risk_free_rate
    n_assets = len(tickers)
    if n_assets == 0:
        raise ValueError("no assets to optimize")

    weights = cp.Variable(n_assets)
    portfolio_return = mu @ weights
    portfolio_variance = cp.quad_form(weights, cov)
    objective = cp.Maximize(risk_tolerance * portfolio_return - (1.0 - risk_tolerance) * portfolio_variance)
    constraints_list = [cp.sum(weights) == 1, weights >= 0]

    # Per-asset cap to prevent concentration. Must never go below 1/n_assets,
    # otherwise n_assets * cap < 1 and the sum-to-1 constraint becomes
    # infeasible for small portfolios (e.g. a 2-asset crypto-only portfolio
    # capped at 25% each can never sum to 100%). It also must never be
    # stricter than an explicit class max bound the caller configured for a
    # given asset's class -- e.g. a "bonds: 20-80%" bound with only one bond
    # asset means that single asset needs to be allowed up to 80%, not
    # silently capped at the generic default and made infeasible.
    base_cap = max(min(max_single_asset_weight, 1.0), 1.0 / n_assets)
    if n_assets > 1:
        if constraints is not None:
            class_max_by_asset_class = {
                _CLASS_ALIASES[schema_name]: bounds["max"]
                for schema_name, bounds in constraints.model_dump().items()
                if schema_name in _CLASS_ALIASES
            }
            per_asset_cap = np.array(
                [max(base_cap, class_max_by_asset_class.get(asset_class, 0.0)) for asset_class in asset_classes]
            )
            constraints_list.append(weights <= per_asset_cap)
        else:
            constraints_list.append(weights <= base_cap)

    if constraints is not None:
        constraints_list.extend(_build_class_constraints(weights, asset_classes, constraints))

    problem = cp.Problem(objective, constraints_list)
    last_error: Exception | None = None
    for solver in (cp.CLARABEL, cp.OSQP, cp.SCS):
        try:
            problem.solve(solver=solver, verbose=False)
            last_error = None
            break
        except Exception as exc:
            last_error = exc
            continue

    if last_error is not None:
        raise ValueError(f"optimization failed: {last_error}") from last_error
    if problem.status not in {cp.OPTIMAL, cp.OPTIMAL_INACCURATE}:
        raise ValueError(f"optimization failed: {problem.status}")

    resolved = np.array(weights.value).clip(0, 1)
    total = resolved.sum()
    if total <= 0:
        raise ValueError("optimizer produced invalid weights")
    resolved /= total
    return {ticker: float(resolved[index]) for index, ticker in enumerate(tickers)}


def efficient_frontier(
    mu: np.ndarray,
    cov: np.ndarray,
    tickers: list[str],
    asset_classes: list[str],
    constraints: Optional[PortfolioConstraints],
    n_points: int = 50,
    risk_free_rate: float = 0.065,
) -> list[FrontierPoint]:
    points: list[FrontierPoint] = []
    for risk_tolerance in np.linspace(0.0, 1.0, n_points):
        try:
            weight_map = constrained_mvo(
                mu=mu,
                cov=cov,
                tickers=tickers,
                asset_classes=asset_classes,
                constraints=constraints,
                risk_tolerance=float(risk_tolerance),
                risk_free_rate=risk_free_rate,
            )
        except Exception:
            continue

        weight_array = np.array([weight_map[ticker] for ticker in tickers])
        expected_return = float(mu @ weight_array)
        volatility = float(np.sqrt(weight_array @ cov @ weight_array))
        sharpe = (expected_return - risk_free_rate) / volatility if volatility > 0 else 0.0
        points.append(
            FrontierPoint(
                expected_return=expected_return,
                volatility=volatility,
                sharpe=sharpe,
                weights=weight_map,
            )
        )
    return points


def _build_class_constraints(weights: cp.Variable, asset_classes: list[str], constraints: PortfolioConstraints) -> list:
    resolved_constraints: list = []
    class_map = constraints.model_dump()
    for schema_name, bounds in class_map.items():
        asset_class = _CLASS_ALIASES.get(schema_name)
        if asset_class is None:
            continue
        indexes = [index for index, name in enumerate(asset_classes) if name == asset_class]
        if not indexes:
            continue
        class_weight = cp.sum(weights[indexes])
        resolved_constraints.append(class_weight >= bounds["min"])
        resolved_constraints.append(class_weight <= bounds["max"])
    return resolved_constraints
