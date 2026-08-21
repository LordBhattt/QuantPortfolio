from pathlib import Path
import sys
import asyncio
import logging
from contextlib import asynccontextmanager

CURRENT_DIR = Path(__file__).resolve().parent
PARENT_DIR = CURRENT_DIR.parent
if str(PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(PARENT_DIR))

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

from backend.cache.redis_cache import RedisCache
from backend.config import get_settings
import backend.database as database
from backend.dependencies import set_singletons
from backend.errors import AppError
from backend.quant.data_fetcher import DataFetcher
from backend.quant.forecaster import ReturnForecaster
from backend.quant.regime import RegimeDetector
from backend.rate_limit import limiter
from backend.routers import alerts, analytics, assets, auth, backtest, onboarding, optimization, portfolio, risk
from backend.schemas.common import HealthResponse
from backend.services.asset_service import seed_default_assets
from backend.services.optimization_service import init_ml_models
from backend.tasks.scheduler import create_scheduler

settings = get_settings()
logging.basicConfig(level=logging.DEBUG if settings.DEBUG else logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    del app
    try:
        async with database.engine.begin() as connection:
            await connection.run_sync(database.metadata.create_all)
    except Exception as exc:
        fallback_url = database.build_sqlite_database_url()
        logger.warning("Primary database unavailable, falling back to SQLite at %s: %s", fallback_url, exc)
        database.configure_database(fallback_url)
        async with database.engine.begin() as connection:
            await connection.run_sync(database.metadata.create_all)

    async with database.AsyncSessionLocal() as session:
        await seed_default_assets(session)
        await session.commit()

    cache = RedisCache()
    await cache.connect()
    fetcher = DataFetcher(cache)
    set_singletons(cache, fetcher)

    regime_detector = RegimeDetector(n_states=settings.HMM_N_STATES)
    forecaster = ReturnForecaster()

    try:
        spy_frame = await asyncio.wait_for(
            fetcher.get_price_history("SPY", "yahoo", days=365),
            timeout=30,
        )
        spy_returns = spy_frame["close"].pct_change().dropna()
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(None, regime_detector.fit, spy_returns)
        logger.info("regime detector initialized")
    except Exception as exc:
        logger.warning("regime detector initialization skipped: %s", exc)

    try:
        forecaster.load()
        logger.info("return forecaster loaded")
    except Exception as exc:
        logger.warning("return forecaster unavailable: %s", exc)

    init_ml_models(regime_detector, forecaster)
    scheduler = create_scheduler(regime_detector, fetcher)
    scheduler.start()

    try:
        yield
    finally:
        scheduler.shutdown(wait=False)
        await fetcher.close()
        await cache.disconnect()
        await database.engine.dispose()


app = FastAPI(title="QuantPortfolio API", version="1.0.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    del request
    return JSONResponse(status_code=exc.status_code, content=exc.as_payload())


@app.exception_handler(RateLimitExceeded)
async def rate_limit_error_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    del request, exc
    return JSONResponse(
        status_code=429,
        content={
            "error": "Too many requests",
            "code": "rate_limit_exceeded",
            "detail": "Rate limit exceeded",
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    del request
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation failed",
            "code": "validation_error",
            "detail": str(exc),
        },
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    del request
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "Request failed",
            "code": f"http_{exc.status_code}",
            "detail": str(exc.detail),
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled error on %s %s", request.method, request.url.path, exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "code": "internal_server_error",
            "detail": str(exc),
        },
    )


app.include_router(auth.router)
app.include_router(portfolio.router)
app.include_router(assets.router)
app.include_router(alerts.router)
app.include_router(onboarding.router)
app.include_router(optimization.router)
app.include_router(risk.router)
app.include_router(analytics.router)
app.include_router(backtest.router)


@app.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    return HealthResponse(status="ok", version="1.0.0")
