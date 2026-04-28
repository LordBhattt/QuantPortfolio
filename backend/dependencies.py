from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from backend.cache.redis_cache import RedisCache
from backend.data_types import CurrentUser
from backend.database import get_db
from backend.errors import AppError
from backend.quant.data_fetcher import DataFetcher
from backend.services.auth_service import decode_token, get_user_by_id

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/token")

_cache: RedisCache | None = None
_fetcher: DataFetcher | None = None


def set_singletons(cache: RedisCache, fetcher: DataFetcher) -> None:
    global _cache, _fetcher
    _cache = cache
    _fetcher = fetcher


def get_cache() -> RedisCache:
    if _cache is None:
        raise AppError("Dependency unavailable", "cache_not_ready", "Cache has not been initialized", 503)
    return _cache


def get_fetcher() -> DataFetcher:
    if _fetcher is None:
        raise AppError("Dependency unavailable", "fetcher_not_ready", "Data fetcher has not been initialized", 503)
    return _fetcher


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> CurrentUser:
    token_data = decode_token(token)
    user = await get_user_by_id(token_data.user_id, db)
    if user is None or not user.is_active:
        raise AppError("Authentication failed", "user_not_found", "User not found or inactive", 401)
    return CurrentUser(id=user.id, email=user.email, full_name=user.full_name, is_active=user.is_active)
