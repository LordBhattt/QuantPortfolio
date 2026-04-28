"""Constrained mean-variance optimization."""

from typing import Optional

import cvxpy as cp
import numpy as np

from backend.schemas.optimization import FrontierPoint, PortfolioConstraints


def constrained_mvo(
    mu: np.ndarray,
    cov: np.ndarray,
    tickers: list[str],
    asset_classes: list[str],
    constraints: Optional[PortfolioConstraints],
    risk_tolerance: float,
    risk_free_rate: float = 0.065,
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
    aliases = {
        "stocks": "stock",
        "crypto": "crypto",
        "gold": "gold",
        "mf_etf": "mf_etf",
        "bonds": "bond",
    }
    for schema_name, bounds in class_map.items():
        asset_class = aliases.get(schema_name)
        if asset_class is None:
            continue
        indexes = [index for index, name in enumerate(asset_classes) if name == asset_class]
        if not indexes:
            continue
        class_weight = cp.sum(weights[indexes])
        resolved_constraints.append(class_weight >= bounds["min"])
        resolved_constraints.append(class_weight <= bounds["max"])
    return resolved_constraints
