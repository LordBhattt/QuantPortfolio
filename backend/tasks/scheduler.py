import asyncio
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.quant.regime import RegimeDetector

logger = logging.getLogger(__name__)


def create_scheduler(regime_detector: RegimeDetector, fetcher) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()

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

    async def trigger_lstm_retrain() -> None:
        logger.info("scheduled LSTM retraining trigger fired; run backend.ml.trainer offline with fresh data")

    scheduler.add_job(refresh_price_cache, CronTrigger(minute=0), name="refresh_price_cache")
    scheduler.add_job(refit_regime_detector, CronTrigger(day_of_week="sun", hour=2), name="refit_regime_detector")
    scheduler.add_job(trigger_lstm_retrain, CronTrigger(day=1, hour=3), name="trigger_lstm_retrain")
    return scheduler
