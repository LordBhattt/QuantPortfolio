import hashlib
import logging

from fastapi import APIRouter, Depends, Request
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from backend.cache.redis_cache import RedisCache
from backend.config import get_settings
from backend.data_types import CurrentUser
from backend.database import get_db
from backend.dependencies import get_cache, get_current_user, get_fetcher
from backend.quant.data_fetcher import DataFetcher
from backend.schemas.backtest import BacktestRequest, BacktestResponse
from backend.services.backtest_service import run_backtest_service
from backend.services.optimization_service import get_ml_models

settings = get_settings()
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/backtest", tags=["backtest"])
limiter = Limiter(key_func=get_remote_address)


@router.post("/", response_model=BacktestResponse)
@router.post("", response_model=BacktestResponse, include_in_schema=False)
@limiter.limit("20/minute")
async def run_backtest_endpoint(
    request: Request,
    payload: BacktestRequest,
    db: AsyncSession = Depends(get_db),
    fetcher: DataFetcher = Depends(get_fetcher),
    cache: RedisCache = Depends(get_cache),
    current_user: CurrentUser = Depends(get_current_user),
) -> BacktestResponse:
    del request
    payload_json = payload.model_dump_json()
    req_hash = hashlib.sha256(payload_json.encode()).hexdigest()[:16]
    cache_key = f"backtest:{payload.portfolio_id}:{req_hash}"

    try:
        cached_raw = await cache.get(cache_key)
        if cached_raw:
            return BacktestResponse.model_validate_json(cached_raw)
    except Exception as exc:
        logger.warning("Cache lookup error for %s: %s", cache_key, exc)

    regime_detector, forecaster = get_ml_models()
    result = await run_backtest_service(
        request=payload,
        db=db,
        fetcher=fetcher,
        regime_detector=regime_detector,
        forecaster=forecaster,
        user_id=current_user.id,
    )

    ttl = getattr(settings, "BACKTEST_CACHE_TTL_SECONDS", 3600)
    try:
        await cache.set(cache_key, result.model_dump_json(), ttl=ttl)
    except Exception as exc:
        logger.warning("Cache write error for %s: %s", cache_key, exc)

    return result
