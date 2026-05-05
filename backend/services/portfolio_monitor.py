from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.errors import AppError
from backend.models.asset import assets
from backend.models.holding import holdings
from backend.models.portfolio import portfolios
from backend.models.portfolio_alert import portfolio_alerts
from backend.models.user import users
from backend.quant.data_fetcher import DataFetcher
from backend.schemas.portfolio_monitor import DriftedAsset, RebalanceAlert
DRIFT_THRESHOLD = 0.05
PEAK_DRAWDOWN_THRESHOLD = 0.10


@dataclass(slots=True)
class AssetValue:
    ticker: str
    asset_class: str
    current_value_inr: float


async def monitor_portfolio(portfolio_id: UUID, db: AsyncSession, fetcher: DataFetcher) -> RebalanceAlert | None:
    portfolio_result = await db.execute(select(portfolios).where(portfolios.c.id == portfolio_id))
    portfolio_row = portfolio_result.mappings().first()
    if portfolio_row is None:
        return None

    holding_result = await db.execute(select(holdings).where(holdings.c.portfolio_id == portfolio_id))
    holding_rows = [dict(row) for row in holding_result.mappings().all()]
    if not holding_rows:
        return None

    tickers = [row["ticker"] for row in holding_rows]
    asset_rows: list[dict] = []
    if tickers:
        asset_result = await db.execute(select(assets).where(assets.c.ticker.in_(tickers)))
        asset_rows = [dict(row) for row in asset_result.mappings().all()]

    asset_map = {row["ticker"]: row for row in asset_rows}
    usd_inr_rate = await fetcher.get_usd_inr_rate()
    current_asset_values = await _fetch_asset_values(holding_rows, asset_map, fetcher, usd_inr_rate)
    if not current_asset_values:
        return None

    total_value_inr = float(sum(item.current_value_inr for item in current_asset_values))
    if total_value_inr <= 0:
        return None

    current_class_weights = _aggregate_class_weights(current_asset_values, total_value_inr)
    target_weights = portfolio_row.get("last_optimized_weights") or {}

    drifted_assets = _collect_drifted_assets(current_asset_values, current_class_weights, target_weights)
    peak_value = portfolio_row.get("peak_value")
    peak_drop_pct = None
    peak_alert = False

    if peak_value is None or total_value_inr > float(peak_value):
        await db.execute(
            update(portfolios).where(portfolios.c.id == portfolio_id).values(peak_value=total_value_inr)
        )
        peak_value = total_value_inr
    elif float(peak_value) > 0:
        peak_drop_pct = (float(peak_value) - total_value_inr) / float(peak_value)
        peak_alert = peak_drop_pct > PEAK_DRAWDOWN_THRESHOLD

    if not drifted_assets and not peak_alert:
        return None

    triggered_at = datetime.now(timezone.utc)
    message = _build_alert_message(drifted_assets, peak_alert, peak_drop_pct)
    return RebalanceAlert(
        portfolio_id=portfolio_id,
        triggered_at=triggered_at,
        drifted_assets=drifted_assets,
        recommended_action="rebalance",
        current_value_inr=total_value_inr,
        peak_value_inr=float(peak_value) if peak_value is not None else None,
        peak_drop_pct=peak_drop_pct,
        message=message,
    )


async def monitor_all_active_portfolios(
    db: AsyncSession,
    fetcher: DataFetcher,
    persist_alerts: bool = False,
) -> list[RebalanceAlert]:
    result = await db.execute(
        select(portfolios.c.id)
        .select_from(portfolios.join(users, portfolios.c.user_id == users.c.id))
        .where(users.c.is_active.is_(True))
        .order_by(portfolios.c.created_at.asc())
    )
    portfolio_ids = [row[0] for row in result.all()]

    alerts: list[RebalanceAlert] = []
    for portfolio_id in portfolio_ids:
        alert = await monitor_portfolio(portfolio_id, db, fetcher)
        if alert is None:
            continue
        alerts.append(alert)
        if persist_alerts:
            await db.execute(
                insert(portfolio_alerts).values(
                    portfolio_id=portfolio_id,
                    alert_type=alert.recommended_action,
                    message=alert.message,
                    is_read=False,
                )
            )

    return alerts


async def store_portfolio_alerts(alerts: list[RebalanceAlert], db: AsyncSession) -> None:
    for alert in alerts:
        await db.execute(
            insert(portfolio_alerts).values(
                portfolio_id=alert.portfolio_id,
                alert_type=alert.recommended_action,
                message=alert.message,
                is_read=False,
            )
        )


async def _fetch_asset_values(
    holding_rows: list[dict],
    asset_map: dict[str, dict],
    fetcher: DataFetcher,
    usd_inr_rate: float,
) -> list[AssetValue]:
    price_tasks = []
    task_meta: list[tuple[dict, dict]] = []
    for row in holding_rows:
        ticker = row["ticker"]
        asset_row = asset_map.get(ticker)
        if asset_row is None:
            continue
        price_tasks.append(fetcher.get_price_history(ticker, asset_row["data_source"], days=5))
        task_meta.append((row, asset_row))

    if not price_tasks:
        return []

    price_frames = await asyncio.gather(*price_tasks)
    values: list[AssetValue] = []
    for (holding, asset_row), frame in zip(task_meta, price_frames):
        ticker = holding["ticker"]
        if frame.empty:
            continue
        latest_price = float(frame["close"].iloc[-1])
        quantity = float(holding["quantity"])
        currency = asset_row["currency"].upper()
        current_value_inr = latest_price * quantity * (usd_inr_rate if currency != "INR" else 1.0)
        values.append(
            AssetValue(
                ticker=ticker,
                asset_class=asset_row["asset_class"].value,
                current_value_inr=float(current_value_inr),
            )
        )

    return values


def _aggregate_class_weights(asset_values: list[AssetValue], total_value_inr: float) -> dict[str, float]:
    class_values: dict[str, float] = defaultdict(float)
    for item in asset_values:
        class_values[item.asset_class] += item.current_value_inr
    return {asset_class: value / total_value_inr for asset_class, value in class_values.items()}


def _collect_drifted_assets(
    asset_values: list[AssetValue],
    current_class_weights: dict[str, float],
    target_weights: dict,
) -> list[DriftedAsset]:
    drifted_assets: list[DriftedAsset] = []
    for asset_class, current_weight in current_class_weights.items():
        target_weight = target_weights.get(asset_class)
        if target_weight is None:
                        continue
        drift = abs(float(current_weight) - float(target_weight))
        if drift <= DRIFT_THRESHOLD:
            continue
        for item in asset_values:
            if item.asset_class == asset_class:
                drifted_assets.append(
                    DriftedAsset(
                        ticker=item.ticker,
                        asset_class=asset_class,
                        current_weight=float(current_weight),
                        target_weight=float(target_weight),
                        drift=float(drift),
                    )
                )
    return drifted_assets


def _build_alert_message(drifted_assets: list[DriftedAsset], peak_alert: bool, peak_drop_pct: float | None) -> str:
    parts: list[str] = []
    if drifted_assets:
        tickers = ", ".join(item.ticker for item in drifted_assets)
        parts.append(f"Allocation drift exceeded 5% for {tickers}")
    if peak_alert and peak_drop_pct is not None:
        parts.append(f"Portfolio value dropped {peak_drop_pct * 100:.1f}% from the last peak")
    return "; ".join(parts) if parts else "Rebalance conditions met"