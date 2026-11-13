"""Leakage-safe candidate selection for the QP Smart backtest strategy."""

from dataclasses import dataclass
from typing import Any, Callable

import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import linkage, leaves_list
from scipy.optimize import minimize
from scipy.spatial.distance import squareform
from sklearn.ensemble import GradientBoostingRegressor


@dataclass(frozen=True)
class SmartConfig:
    name: str
    family: str
    shrink_lambda: float = 1.0
    no_trade_band: float = 0.0
    rebalance_days: int = 21
    vol_target: float | None = None
    bear_cut: float = 0.0

    def label(self) -> str:
        parts = [self.name]
        if self.shrink_lambda < 1:
            parts.append(f"lambda={self.shrink_lambda:g}")
        if self.no_trade_band:
            parts.append(f"band={self.no_trade_band:.0%}")
        if self.rebalance_days == 63:
            parts.append("quarterly")
        if self.vol_target:
            parts.append(f"target={self.vol_target:.0%}")
        if self.bear_cut:
            parts.append(f"bear-cut={self.bear_cut:.0%}")
        return ", ".join(parts)


def candidate_configs() -> list[SmartConfig]:
    configs = [
        SmartConfig("Shrinkage", "shrink", shrink_lambda=value)
        for value in (0.0, 0.25, 0.5, 0.75, 1.0)
    ]
    configs.extend(
        SmartConfig("No-trade", "optimizer", no_trade_band=band, rebalance_days=days)
        for band in (0.02, 0.05, 0.10)
        for days in (21, 63)
    )
    configs.extend(
        [
            SmartConfig("Inverse Volatility", "inverse_vol"),
            SmartConfig("Risk Parity", "risk_parity"),
            SmartConfig("Hierarchical Risk Parity", "hrp"),
            SmartConfig("Volatility Model", "vol_model"),
            SmartConfig("Vol Target + Bear Overlay", "overlay", vol_target=0.12, bear_cut=0.30),
        ]
    )
    return configs


def _bounds_by_class(constraints: Any) -> dict[str, dict[str, float]]:
    if constraints is None:
        return {}
    values = constraints.model_dump() if hasattr(constraints, "model_dump") else constraints
    aliases = {"stocks": "stock", "bonds": "bond"}
    return {
        aliases.get(key, key): {"min": float(value["min"]), "max": float(value["max"])}
        for key, value in values.items()
    }


def project_class_bounds(
    weights: np.ndarray,
    asset_classes: list[str],
    constraints: Any,
) -> np.ndarray:
    """Keep risk-based candidates inside the same class bounds as the optimizer."""
    result = np.maximum(np.asarray(weights, dtype=float), 0.0)
    if result.sum() <= 0:
        result = np.ones(len(asset_classes), dtype=float)
    result /= result.sum()
    bounds = _bounds_by_class(constraints)
    if not bounds:
        return result

    for _ in range(8):
        class_indices: dict[str, list[int]] = {}
        for index, asset_class in enumerate(asset_classes):
            class_indices.setdefault(asset_class, []).append(index)
        changed = False
        for asset_class, indices in class_indices.items():
            bound = bounds.get(asset_class)
            if not bound:
                continue
            total = float(result[indices].sum())
            if total > bound["max"] and total > 0:
                result[indices] *= bound["max"] / total
                changed = True
            elif total < bound["min"]:
                result[indices] += (bound["min"] - total) / len(indices)
                changed = True
        if not changed:
            break
        result = np.maximum(result, 0.0)
        result /= result.sum()
    return result


def _inverse_vol(returns: pd.DataFrame) -> np.ndarray:
    vol = returns.std().to_numpy(dtype=float) * np.sqrt(252)
    inv = 1.0 / np.maximum(vol, 1e-8)
    return inv / inv.sum()


def _risk_parity(returns: pd.DataFrame) -> np.ndarray:
    cov = returns.cov().to_numpy(dtype=float) * 252
    cov += np.eye(len(cov)) * 1e-8

    def objective(weights: np.ndarray) -> float:
        portfolio_vol = np.sqrt(max(float(weights @ cov @ weights), 1e-12))
        contributions = weights * (cov @ weights) / portfolio_vol
        target = np.full(len(weights), portfolio_vol / len(weights))
        return float(np.sum((contributions - target) ** 2))

    result = minimize(
        objective,
        np.full(len(cov), 1.0 / len(cov)),
        method="SLSQP",
        bounds=[(0.0, 1.0)] * len(cov),
        constraints={"type": "eq", "fun": lambda weights: weights.sum() - 1.0},
        options={"maxiter": 300, "ftol": 1e-10},
    )
    return result.x if result.success else _inverse_vol(returns)


def _hrp(returns: pd.DataFrame) -> np.ndarray:
    corr = returns.corr().fillna(0.0).clip(-1.0, 1.0)
    distance = np.sqrt(np.maximum((1.0 - corr) / 2.0, 0.0))
    if len(corr) == 1:
        return np.ones(1)
    order = leaves_list(linkage(squareform(distance.to_numpy(), checks=False), method="single"))
    cov = returns.cov().to_numpy(dtype=float) * 252
    weights = np.zeros(len(corr))
    clusters = [list(order)]
    weights[order] = 1.0
    while clusters:
        next_clusters: list[list[int]] = []
        for cluster in clusters:
            if len(cluster) <= 1:
                continue
            midpoint = len(cluster) // 2
            left, right = cluster[:midpoint], cluster[midpoint:]
            left_var = float(np.mean(np.diag(cov)[left]))
            right_var = float(np.mean(np.diag(cov)[right]))
            left_share = right_var / max(left_var + right_var, 1e-12)
            weights[left] *= left_share
            weights[right] *= 1.0 - left_share
            next_clusters.extend([left, right])
        clusters = next_clusters
    if weights.sum() <= 0:
        return _inverse_vol(returns)
    return weights / weights.sum()


def _vol_features(returns: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    rows: list[np.ndarray] = []
    targets: list[np.ndarray] = []
    for index in range(63, len(returns) - 21):
        history = returns.iloc[:index]
        features = np.concatenate(
            [
                history.tail(window).std().to_numpy() * np.sqrt(252)
                for window in (5, 21, 63)
            ]
        )
        rows.append(features)
        forward = returns.iloc[index:index + 21]
        targets.append(np.sqrt(np.square(forward.to_numpy()).mean(axis=0) * 252))
    return np.asarray(rows), np.asarray(targets)


def fit_vol_models(returns: pd.DataFrame) -> list[GradientBoostingRegressor] | None:
    features, targets = _vol_features(returns)
    if len(features) < 12:
        return None
    models: list[GradientBoostingRegressor] = []
    for column in range(targets.shape[1]):
        model = GradientBoostingRegressor(random_state=7, n_estimators=40, max_depth=2)
        model.fit(features, np.log(np.maximum(targets[:, column], 1e-8)))
        models.append(model)
    return models


def forecast_volatility(
    returns: pd.DataFrame,
    models: list[GradientBoostingRegressor] | None,
) -> np.ndarray:
    baseline = returns.tail(63).std().to_numpy(dtype=float) * np.sqrt(252)
    if not models:
        return baseline
    features = np.concatenate(
        [returns.tail(window).std().to_numpy() * np.sqrt(252) for window in (5, 21, 63)]
    ).reshape(1, -1)
    return np.maximum(np.exp(np.asarray([model.predict(features)[0] for model in models])), 1e-8)


def vol_model_error(
    train_returns: pd.DataFrame,
    test_returns: pd.DataFrame,
) -> dict[str, float]:
    models = fit_vol_models(train_returns)
    if models is None or len(test_returns) < 21:
        return {"model_mae": 0.0, "baseline_mae": 0.0, "model_beats_baseline": False}
    errors_model: list[float] = []
    errors_baseline: list[float] = []
    for index in range(0, len(test_returns) - 21, 21):
        history = pd.concat([train_returns, test_returns.iloc[:index]])
        actual_window = test_returns.iloc[index:index + 21]
        actual = np.sqrt(np.square(actual_window.to_numpy()).mean(axis=0) * 252)
        predicted = forecast_volatility(history, models)
        baseline_window = history.tail(63)
        baseline = np.sqrt(np.square(baseline_window.to_numpy()).mean(axis=0) * 252)
        errors_model.append(float(np.mean(np.abs(predicted - actual))))
        errors_baseline.append(float(np.mean(np.abs(baseline - actual))))
    model_mae = float(np.mean(errors_model)) if errors_model else 0.0
    baseline_mae = float(np.mean(errors_baseline)) if errors_baseline else 0.0
    return {
        "model_mae": model_mae,
        "baseline_mae": baseline_mae,
        "model_beats_baseline": model_mae < baseline_mae,
    }


def smart_weights(
    returns: pd.DataFrame,
    tickers: list[str],
    asset_classes: list[str],
    constraints: Any,
    config: SmartConfig,
    optimizer: Callable[[pd.DataFrame, list[str], list[str]], dict[str, float]],
    previous_weights: dict[str, float] | None = None,
    regime: str | None = None,
    vol_models: list[GradientBoostingRegressor] | None = None,
) -> dict[str, float]:
    base = optimizer(returns, tickers, asset_classes)
    equal = np.full(len(tickers), 1.0 / len(tickers))

    if config.family == "shrink":
        weights = config.shrink_lambda * np.array([base[t] for t in tickers]) + (1 - config.shrink_lambda) * equal
    elif config.family == "inverse_vol":
        weights = _inverse_vol(returns)
    elif config.family == "risk_parity":
        weights = _risk_parity(returns)
    elif config.family == "hrp":
        weights = _hrp(returns)
    elif config.family == "vol_model":
        forecast = forecast_volatility(returns, vol_models)
        weights = 1.0 / np.maximum(forecast, 1e-8)
        weights /= weights.sum()
    else:
        weights = np.array([base[t] for t in tickers])

    if config.bear_cut and regime == "bear":
        risky = np.array([asset_class in {"stock", "crypto"} for asset_class in asset_classes])
        safe = np.array([asset_class in {"bond", "gold"} for asset_class in asset_classes])
        transfer = float(weights[risky].sum()) * config.bear_cut
        weights[risky] *= 1.0 - config.bear_cut
        if safe.any():
            weights[safe] += transfer / safe.sum()

    if config.vol_target:
        annual_cov = returns.cov().to_numpy() * 252
        annual_vol = float(np.sqrt(max(weights @ annual_cov @ weights, 0.0)))
        if annual_vol > config.vol_target:
            risky = np.array([asset_class not in {"bond", "gold"} for asset_class in asset_classes])
            safe = ~risky
            scale = config.vol_target / annual_vol
            transfer = float(weights[risky].sum()) * (1.0 - scale)
            weights[risky] *= scale
            if safe.any():
                weights[safe] += transfer / safe.sum()

    weights = project_class_bounds(weights, asset_classes, constraints)
    proposed = {ticker: float(weight) for ticker, weight in zip(tickers, weights)}
    if previous_weights and config.no_trade_band:
        bounded = np.array([
            previous_weights.get(ticker, 0.0)
            if abs(proposed.get(ticker, 0.0) - previous_weights.get(ticker, 0.0)) <= config.no_trade_band
            else proposed.get(ticker, 0.0)
            for ticker in tickers
        ])
        bounded = np.maximum(bounded, 0.0)
        if bounded.sum() > 0:
            bounded /= bounded.sum()
        proposed = {ticker: float(weight) for ticker, weight in zip(tickers, bounded)}
    return proposed


def select_config(
    prices: pd.DataFrame,
    split_date: pd.Timestamp,
    evaluate: Callable[[SmartConfig, pd.DataFrame], float],
) -> tuple[SmartConfig, dict[str, float]]:
    """Select solely from prices at or before split_date."""
    train = prices.loc[:split_date]
    if train.empty or train.index.max() > split_date:
        raise AssertionError("config selection received data after the split date")
    scores = {config.label(): float(evaluate(config, train)) for config in candidate_configs()}
    best_label = max(scores, key=scores.get)
    best = next(config for config in candidate_configs() if config.label() == best_label)
    return best, scores


def select_config_rolling(
    prices: pd.DataFrame,
    split_date: pd.Timestamp,
    evaluate: Callable[[SmartConfig, pd.DataFrame], float],
    windows: int = 4,
    variance_penalty: float = 0.25,
) -> tuple[SmartConfig, dict[str, float]]:
    """Select using only several pre-split expanding windows."""
    train = prices.loc[:split_date]
    if train.empty or train.index.max() > split_date:
        raise AssertionError("config selection received data after the split date")
    endpoints = np.linspace(max(30, int(len(train) * 0.35)), len(train), windows).astype(int)
    scores: dict[str, float] = {}
    for config in candidate_configs():
        window_scores = [
            float(evaluate(config, train.iloc[:int(endpoint)]))
            for endpoint in endpoints
        ]
        scores[config.label()] = float(np.mean(window_scores) - variance_penalty * np.std(window_scores))
    best_label = max(scores, key=scores.get)
    best = next(config for config in candidate_configs() if config.label() == best_label)
    return best, scores
