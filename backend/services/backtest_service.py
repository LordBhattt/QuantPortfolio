"""Service layer for walk-forward backtest."""

import asyncio
import logging
from typing import Any
from uuid import UUID

import pandas as pd
from sqlalchemy import select

from backend.config import get_settings
from backend.models.asset import assets
from backend.models.holding import holdings
from backend.models.portfolio import portfolios
from backend.errors import AppError
from backend.quant.backtest import run_backtest
from backend.schemas.backtest import BacktestRequest, BacktestResponse, StrategyMetrics
from backend.schemas.optimization import PortfolioConstraints
from backend.services.portfolio_service import _merge_holdings_rows, load_portfolio_snapshot

settings = get_settings()
logger = logging.getLogger(__name__)


async def run_backtest_service(
    request: BacktestRequest,
    db: Any,
    fetcher: Any,
    regime_detector: Any,
    forecaster: Any,
    user_id: UUID | None = None,
) -> BacktestResponse:
    """
    Run walk-forward backtest for a portfolio.

    Steps:
    1. Load portfolio holdings and asset metadata
    2. Fetch prices for all tickers for lookback_years + 1 extra year of history
    3. Fetch SPY and NIFTYBEES.NS as benchmarks
    4. Build aligned prices DataFrame
    5. Call run_backtest()
    6. Build BacktestResponse with headline card
    """
    loop = asyncio.get_running_loop()

    try:
        portfolio_uuid = UUID(request.portfolio_id)
    except Exception:
        raise AppError("Backtest failed", "invalid_portfolio_id", "Invalid portfolio ID", 400)

    # 1. Load portfolio holdings and asset metadata
    if user_id is not None:
        portfolio, holding_rows, asset_rows = await load_portfolio_snapshot(portfolio_uuid, user_id, db)
    else:
        result = await db.execute(select(portfolios).where(portfolios.c.id == portfolio_uuid))
        row = result.mappings().first()
        if row is None:
            raise AppError("Portfolio not found", "portfolio_not_found", "Portfolio not found", 404)
        portfolio = dict(row)

        holdings_res = await db.execute(select(holdings).where(holdings.c.portfolio_id == portfolio_uuid))
        holding_rows = _merge_holdings_rows(holdings_res.mappings().all())
        tickers_list = [r["ticker"] for r in holding_rows]
        asset_rows = []
        if tickers_list:
            asset_res = await db.execute(select(assets).where(assets.c.ticker.in_(tickers_list)))
            asset_rows = [dict(r) for r in asset_res.mappings().all()]

    if not holding_rows:
        raise AppError("Backtest failed", "empty_portfolio", "Portfolio has no holdings", 400)

    asset_map = {row["ticker"]: row for row in asset_rows}
    missing = [row["ticker"] for row in holding_rows if row["ticker"] not in asset_map]
    if missing:
        raise AppError(
            "Backtest failed",
            "missing_asset_metadata",
            f"Missing asset metadata for: {', '.join(missing)}",
            400,
        )

    tickers = [row["ticker"] for row in holding_rows]
    asset_classes = [asset_map[t]["asset_class"].value if hasattr(asset_map[t]["asset_class"], "value") else str(asset_map[t]["asset_class"]) for t in tickers]

    # Constraints
    raw_constraints = portfolio.get("constraints") or {}
    constraints = PortfolioConstraints(**raw_constraints) if raw_constraints else None

    # 2. Fetch prices for lookback_years + 1 extra year of history
    total_days = (request.lookback_years + 1) * 365 + 30

    price_results = await asyncio.gather(
        *[
            fetcher.get_price_history(
                ticker=t,
                source=asset_map[t]["data_source"],
                days=total_days,
            )
            for t in tickers
        ],
        return_exceptions=True,
    )

    price_data: dict[str, pd.DataFrame] = {}
    for t, frame in zip(tickers, price_results):
        if isinstance(frame, Exception):
            logger.warning("Price history fetch failed for %s: %s", t, frame)
            continue
        if frame is not None and not frame.empty:
            price_data[t] = frame

    valid_tickers = [t for t in tickers if t in price_data]
    if not valid_tickers:
        raise AppError("Backtest failed", "market_data_unavailable", "Market data unavailable for portfolio assets", 503)

    valid_asset_classes = [asset_classes[tickers.index(t)] for t in valid_tickers]

    # 3. Fetch benchmarks (SPY and NIFTYBEES.NS)
    bench_results = await asyncio.gather(
        fetcher.get_price_history("SPY", "yahoo", days=total_days),
        fetcher.get_price_history("NIFTYBEES.NS", "yahoo", days=total_days),
        return_exceptions=True,
    )
    for bench_name, frame in zip(["SPY", "NIFTYBEES.NS"], bench_results):
        if not isinstance(frame, Exception) and frame is not None and not frame.empty:
            price_data[bench_name] = frame

    # 4. Build aligned prices DataFrame
    close_series_dict: dict[str, pd.Series] = {}
    for t, frame in price_data.items():
        col = "close" if "close" in frame.columns else ("Close" if "Close" in frame.columns else frame.columns[0])
        s = frame[col].dropna()
        if hasattr(s.index, "tz") and s.index.tz is not None:
            s.index = s.index.tz_localize(None)
        close_series_dict[t] = s

    prices_df = pd.DataFrame(close_series_dict)
    prices_df.index = pd.to_datetime(prices_df.index)
    prices_df = prices_df.sort_index().ffill().dropna(how="all")

    # Filter to dates where at least one valid ticker has price
    prices_df = prices_df.dropna(subset=valid_tickers, how="all")
    if len(prices_df) < 30:
        raise AppError("Backtest failed", "insufficient_history", "Insufficient price history for backtest", 400)

    # 5. Call run_backtest
    try:
        backtest_result = await loop.run_in_executor(
            None,
            lambda: run_backtest(
                prices=prices_df,
                tickers=valid_tickers,
                asset_classes=valid_asset_classes,
                constraints=constraints,
                lookback_years=request.lookback_years,
                rebalance=request.rebalance,
                risk_tolerance=request.risk_tolerance,
                cost_bps=float(request.cost_bps),
                use_ml=request.use_ml,
                use_regime=request.use_regime,
                regime_detector=regime_detector,
                forecaster=forecaster,
                initial_value=100000.0,
            ),
        )
    except ValueError as exc:
        raise AppError("Backtest failed", "backtest_computation_error", str(exc), 400)

    # 6. Build BacktestResponse
    strategy_names: list[str] = backtest_result["strategy_names"]
    metrics_by_strat: dict = backtest_result["metrics"]
    equity_curves: dict = backtest_result["equity_curves"]
    weights_history: list = backtest_result["weights_history"]
    years: float = backtest_result["years"]

    strategies_out: list[StrategyMetrics] = []
    equity_curves_out: dict = {}
    drawdown_curves_out: dict = {}

    for strat in strategy_names:
        m = metrics_by_strat[strat]
        strategies_out.append(
            StrategyMetrics(
                name=strat,
                final_value=m["final_value"],
                total_profit_inr=m["total_profit_inr"],
                cagr=m["cagr"],
                volatility=m["volatility"],
                sharpe=m["sharpe"],
                sortino=m["sortino"],
                max_drawdown=m["max_drawdown"],
                calmar=m["calmar"],
                avg_turnover=m["avg_turnover"],
            )
        )

        eq = equity_curves[strat]
        equity_curves_out[strat] = [
            {"date": str(d.date() if hasattr(d, "date") else d), "value": round(float(v), 2)}
            for d, v in zip(eq.index, eq.values)
        ]

        dd = m.get("drawdown_series", pd.Series(dtype=float))
        drawdown_curves_out[strat] = [
            {"date": str(d.date() if hasattr(d, "date") else d), "drawdown": round(float(v), 4)}
            for d, v in zip(dd.index, dd.values)
        ]

    # Best strategy by Sharpe ratio
    best_strategy = max(strategy_names, key=lambda s: metrics_by_strat[s]["sharpe"])

    # Headline comparison: Optimized vs Equal Weight
    opt_profit = metrics_by_strat.get("Optimized", {}).get("total_profit_inr", 0.0)
    eq_profit = metrics_by_strat.get("Equal Weight", {}).get("total_profit_inr", 0.0)
    diff = opt_profit - eq_profit
    years_rounded = int(round(years))

    if diff > 0:
        headline = f"Optimized beat Equal Weight by +INR {diff:,.0f} over {years_rounded}Y"
    elif diff < 0:
        headline = f"Optimized lagged Equal Weight by -INR {abs(diff):,.0f} over {years_rounded}Y"
    else:
        headline = f"Optimized matched Equal Weight over {years_rounded}Y"

    return BacktestResponse(
        strategies=strategies_out,
        equity_curves=equity_curves_out,
        drawdown_curves=drawdown_curves_out,
        weights_history=weights_history,
        best_strategy=best_strategy,
        headline=headline,
        parameters={
            "portfolio_id": request.portfolio_id,
            "lookback_years": request.lookback_years,
            "rebalance": request.rebalance,
            "risk_tolerance": request.risk_tolerance,
            "cost_bps": request.cost_bps,
            "use_ml": request.use_ml,
            "use_regime": request.use_regime,
        },
    )
