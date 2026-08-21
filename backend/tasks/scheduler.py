import asyncio
from datetime import datetime
import logging
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

import backend.database as database
from backend.quant.regime import RegimeDetector
from backend.services.portfolio_monitor import monitor_all_active_portfolios

logger = logging.getLogger(__name__)

IST = ZoneInfo("Asia/Kolkata")


def create_scheduler(regime_detector: RegimeDetector, fetcher) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=IST)

    async def refresh_price_cache() -> None:
        try:
            await fetcher.cache.invalidate_pattern("prices:*")
            await fetcher.cache.invalidate_pattern("fx:*")
            logger.info("invalidated market data caches")
        except Exception as exc:
            logger.exception("cache refresh failed: %s", exc)

    async def refit_regime_detector() -> None:
        try:
            price_frame = await fetcher.get_price_history("SPY", "yahoo", days=365 * 3)
            returns = price_frame["close"].pct_change().dropna()
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, regime_detector.fit, returns)
            logger.info("refitted regime detector")
        except Exception as exc:
            logger.exception("regime detector refit failed: %s", exc)

    async def run_market_hours_monitor() -> None:
        try:
            now = datetime.now(IST)
            if now.hour == 15 and now.minute > 30:
                return
            async with database.AsyncSessionLocal() as session:
                alerts = await monitor_all_active_portfolios(session, fetcher, persist_alerts=False)
                await session.commit()
                if alerts:
                    logger.info("portfolio monitor flagged %s portfolios during market hours", len(alerts))
        except Exception as exc:
            logger.exception("market-hours portfolio monitoring failed: %s", exc)

    async def run_end_of_day_monitor() -> None:
        try:
            async with database.AsyncSessionLocal() as session:
                alerts = await monitor_all_active_portfolios(session, fetcher, persist_alerts=True)
                await session.commit()
                logger.info("portfolio EOD monitoring stored %s alerts", len(alerts))
        except Exception as exc:
            logger.exception("end-of-day portfolio monitoring failed: %s", exc)

    scheduler.add_job(refresh_price_cache, CronTrigger(minute=0), name="refresh_price_cache")
    scheduler.add_job(refit_regime_detector, CronTrigger(day_of_week="sun", hour=2), name="refit_regime_detector")
    scheduler.add_job(
        run_market_hours_monitor,
        CronTrigger(day_of_week="mon-fri", hour="9-15", minute="15,45", timezone=IST),
        name="portfolio_monitor_market_hours",
    )
    scheduler.add_job(
        run_end_of_day_monitor,
        CronTrigger(day_of_week="mon-fri", hour=15, minute=45, timezone=IST),
        name="portfolio_monitor_eod",
    )
    return scheduler
