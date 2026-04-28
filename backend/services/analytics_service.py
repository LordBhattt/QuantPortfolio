import asyncio
from uuid import UUID

import numpy as np
import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from backend.errors import AppError
from backend.quant.covariance import compute_covariance
from backend.quant.data_fetcher import DataFetcher
from backend.quant.factor_model import fama_french_regression
from backend.quant.returns import align_returns
from backend.schemas.analytics import FactorExposure, PerformanceAttribution, PerformancePoint, PortfolioAnalytics
from backend.services.portfolio_service import load_portfolio_snapshot


async def get_factor_exposure(
    portfolio_id: UUID,
    user_id: UUID,
    db: AsyncSession,
    fetcher: DataFetcher,
) -> FactorExposure:
    loop = asyncio.get_running_loop()
    _, holdings, assets = await load_portfolio_snapshot(portfolio_id, user_id, db)
    if not holdings:
        raise AppError("Factor analysis failed", "empty_portfolio", "Portfolio has no holdings", 400)

    asset_map = {row["ticker"]: row for row in assets}
    tickers = [row["ticker"] for row in holdings if row["ticker"] in asset_map]
    quantities = {row["ticker"]: float(row["quantity"]) for row in holdings}
    asset_currencies = {ticker: asset_map[ticker]["currency"] for ticker in tickers}

    price_frames = await asyncio.gather(
        *[fetcher.get_price_history(ticker, asset_map[ticker]["data_source"], days=365 * 2) for ticker in tickers]
    )
    price_data = dict(zip(tickers, price_frames))
    usd_inr = await fetcher.get_usd_inr_rate()
    returns_df = await loop.run_in_executor(None, align_returns, price_data, asset_currencies, "USD", usd_inr)
    if returns_df.empty:
        raise AppError("Factor analysis failed", "insufficient_returns", "Unable to compute portfolio returns", 400)

    current_values = {
        ticker: float(price_data[ticker]["close"].iloc[-1])
        * quantities[ticker]
        * (1.0 / usd_inr if asset_currencies[ticker].upper() == "INR" else 1.0)
        for ticker in tickers
        if ticker in returns_df.columns
    }
    total_value = float(sum(current_values.values()))
    if total_value <= 0:
        raise AppError("Factor analysis failed", "invalid_portfolio_value", "Portfolio value must be positive", 400)

    common_tickers = list(current_values.keys())
    weights = np.array([current_values[ticker] / total_value for ticker in common_tickers])
    portfolio_returns = returns_df[common_tickers] @ weights
    factors = await fetcher.get_fama_french_factors()
    return await loop.run_in_executor(None, fama_french_regression, portfolio_returns, factors, portfolio_id)


async def get_portfolio_analytics(
    portfolio_id: UUID,
    user_id: UUID,
    db: AsyncSession,
    fetcher: DataFetcher,
) -> PortfolioAnalytics:
    loop = asyncio.get_running_loop()
    _, holdings, assets = await load_portfolio_snapshot(portfolio_id, user_id, db)
    if not holdings:
        raise AppError("Analytics failed", "empty_portfolio", "Portfolio has no holdings", 400)

    asset_map = {row["ticker"]: row for row in assets}
    tickers = [row["ticker"] for row in holdings if row["ticker"] in asset_map]
    quantities = {row["ticker"]: float(row["quantity"]) for row in holdings}
    avg_buy_prices = {row["ticker"]: float(row["avg_buy_price"]) for row in holdings}
    buy_currencies = {row["ticker"]: row["buy_currency"] for row in holdings}
    asset_currencies = {ticker: asset_map[ticker]["currency"] for ticker in tickers}

    price_frames = await asyncio.gather(
        *[fetcher.get_price_history(ticker, asset_map[ticker]["data_source"], days=365) for ticker in tickers]
    )
    price_data = dict(zip(tickers, price_frames))
    usd_inr = await fetcher.get_usd_inr_rate()
    returns_df = await loop.run_in_executor(None, align_returns, price_data, asset_currencies, "USD", usd_inr)

    current_values: dict[str, float] = {}
    cost_basis: dict[str, float] = {}
    day_pnl_by_ticker: dict[str, float] = {}
    total_pnl_by_ticker: dict[str, float] = {}
    allocation_raw: dict[str, float] = {}
    sparkline_by_ticker: dict[str, list[float]] = {}
    price_series_inr: dict[str, pd.Series] = {}

    for ticker in tickers:
        frame = price_data[ticker]
        latest_price = float(frame["close"].iloc[-1])
        previous_close = float(frame["close"].iloc[-2]) if len(frame) > 1 else latest_price
        quantity = quantities[ticker]
        native_multiplier = 1.0 / usd_inr if asset_currencies[ticker].upper() == "INR" else 1.0
        buy_multiplier = 1.0 / usd_inr if buy_currencies[ticker].upper() == "INR" else 1.0
        price_multiplier_inr = 1.0 if asset_currencies[ticker].upper() == "INR" else usd_inr

        current_value = latest_price * quantity * native_multiplier
        invested = avg_buy_prices[ticker] * quantity * buy_multiplier
        day_pnl = (latest_price - previous_close) * quantity * native_multiplier
        total_pnl = current_value - invested
        price_series = frame["close"].astype(float) * price_multiplier_inr
        price_series_inr[ticker] = price_series
        sparkline_by_ticker[ticker] = [float(value) for value in price_series.tail(7).tolist()]

        current_values[ticker] = float(current_value)
        cost_basis[ticker] = float(invested)
        day_pnl_by_ticker[ticker] = float(day_pnl)
        total_pnl_by_ticker[ticker] = float(total_pnl)

        asset_class = asset_map[ticker]["asset_class"].value
        allocation_raw[asset_class] = allocation_raw.get(asset_class, 0.0) + current_value

    total_value_usd = float(sum(current_values.values()))
    if total_value_usd <= 0:
        raise AppError("Analytics failed", "invalid_portfolio_value", "Portfolio value must be positive", 400)

    total_value_inr = float(total_value_usd * usd_inr)
    day_pnl_usd = float(sum(day_pnl_by_ticker.values()))
    day_pnl_inr = float(day_pnl_usd * usd_inr)
    total_pnl_usd = float(sum(total_pnl_by_ticker.values()))
    total_pnl_inr = float(total_pnl_usd * usd_inr)
    invested_usd = float(sum(cost_basis.values()))
    previous_value_usd = total_value_usd - day_pnl_usd
    day_pnl_pct = float(day_pnl_usd / previous_value_usd) if previous_value_usd else 0.0
    total_pnl_pct = float(total_pnl_usd / invested_usd) if invested_usd else 0.0
    asset_class_allocation = {name: float(value / total_value_usd) for name, value in allocation_raw.items()}

    common_tickers = [ticker for ticker in tickers if ticker in returns_df.columns]
    weights = np.array([current_values[ticker] / total_value_usd for ticker in common_tickers])
    portfolio_vol = 0.0
    risk_contributions = {ticker: 0.0 for ticker in tickers}
    if common_tickers:
        cov = await loop.run_in_executor(None, compute_covariance, returns_df[common_tickers], "ledoit_wolf", False, 252)
        portfolio_vol = float(np.sqrt(weights @ cov @ weights))
        if portfolio_vol > 0:
            marginal = cov @ weights
            component = weights * marginal / portfolio_vol
            risk_contributions.update(
                {ticker: float(component[index]) for index, ticker in enumerate(common_tickers)}
            )

    value_series = {
        ticker: series * quantities[ticker]
        for ticker, series in price_series_inr.items()
    }
    performance_series: list[PerformancePoint] = []
    if value_series:
        portfolio_frame = pd.DataFrame(value_series).dropna(how="all").ffill().dropna(how="all")
        if not portfolio_frame.empty:
            portfolio_series = portfolio_frame.sum(axis=1)
            try:
                benchmark_frame = await fetcher.get_price_history("SPY", "yahoo", days=365)
                benchmark_series = (benchmark_frame["close"].astype(float) * usd_inr).reindex(portfolio_series.index).ffill().bfill()
                if not benchmark_series.empty and benchmark_series.iloc[0] != 0:
                    benchmark_series = benchmark_series / benchmark_series.iloc[0] * portfolio_series.iloc[0]
            except Exception:
                benchmark_series = portfolio_series.copy()

            perf_frame = pd.concat(
                [portfolio_series.rename("portfolio"), benchmark_series.rename("benchmark")],
                axis=1,
            ).dropna()
            performance_series = [
                PerformancePoint(
                    date=str(index.date()),
                    portfolio=float(row["portfolio"]),
                    benchmark=float(row["benchmark"]),
                )
                for index, row in perf_frame.iterrows()
            ]

    holdings_breakdown = sorted([
        PerformanceAttribution(
            ticker=ticker,
            name=asset_map[ticker]["name"],
            asset_class=asset_map[ticker]["asset_class"].value,
            weight=float(current_values[ticker] / total_value_usd),
            quantity=float(quantities[ticker]),
            avg_buy_price_inr=float(avg_buy_prices[ticker] if buy_currencies[ticker].upper() == "INR" else avg_buy_prices[ticker] * usd_inr),
            current_price_inr=float(price_series_inr[ticker].iloc[-1]),
            current_value_inr=float(current_values[ticker] * usd_inr),
            pnl_inr=float(total_pnl_by_ticker[ticker] * usd_inr),
            pnl_pct=float(total_pnl_by_ticker[ticker] / cost_basis[ticker]) if cost_basis[ticker] else 0.0,
            sparkline_inr=sparkline_by_ticker.get(ticker, []),
            contribution_to_return=float(total_pnl_by_ticker[ticker] / total_value_usd),
            contribution_to_risk=float(risk_contributions.get(ticker, 0.0)),
        )
        for ticker in tickers
    ], key=lambda item: item.current_value_inr or 0.0, reverse=True)

    factor_exposure = await _safe_factor_exposure(
        portfolio_id=portfolio_id,
        user_id=user_id,
        db=db,
        fetcher=fetcher,
    )

    return PortfolioAnalytics(
        portfolio_id=portfolio_id,
        usd_inr_rate=float(usd_inr),
        total_value_usd=total_value_usd,
        total_value_inr=total_value_inr,
        day_pnl_usd=day_pnl_usd,
        day_pnl_inr=day_pnl_inr,
        day_pnl_pct=day_pnl_pct,
        total_pnl_usd=total_pnl_usd,
        total_pnl_inr=total_pnl_inr,
        total_pnl_pct=total_pnl_pct,
        performance_series=performance_series,
        asset_class_allocation=asset_class_allocation,
        holdings_breakdown=holdings_breakdown,
        factor_exposure=factor_exposure,
    )


async def _safe_factor_exposure(
    portfolio_id: UUID,
    user_id: UUID,
    db: AsyncSession,
    fetcher: DataFetcher,
) -> FactorExposure:
    try:
        return await get_factor_exposure(portfolio_id, user_id, db, fetcher)
    except Exception:
        return FactorExposure(
            portfolio_id=portfolio_id,
            alpha=0.0,
            beta_market=0.0,
            beta_smb=0.0,
            beta_hml=0.0,
            beta_rmw=0.0,
            beta_cma=0.0,
            r_squared=0.0,
            residual_std=0.0,
        )
