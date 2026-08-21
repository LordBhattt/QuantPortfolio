from pathlib import Path
import sys
from collections.abc import AsyncIterator

from sqlalchemy import MetaData
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

CURRENT_DIR = Path(__file__).resolve().parent
PARENT_DIR = CURRENT_DIR.parent
if str(PARENT_DIR) not in sys.path:
    sys.path.insert(0, str(PARENT_DIR))

from backend.config import get_settings

settings = get_settings()
PROJECT_ROOT = CURRENT_DIR.parent
SQLITE_DATABASE_PATH = PROJECT_ROOT / "quantportfolio.db"

metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)


class Base:
    metadata = metadata


def build_sqlite_database_url() -> str:
    return f"sqlite+aiosqlite:///{SQLITE_DATABASE_PATH.as_posix()}"


def _engine_kwargs(database_url: str) -> dict:
    kwargs: dict = {
        "echo": settings.DEBUG,
        "pool_pre_ping": True,
    }
    if not database_url.startswith("sqlite"):
        kwargs["connect_args"] = {"statement_cache_size": 0}
        kwargs["pool_size"] = 10
        kwargs["max_overflow"] = 20
    return kwargs


def _create_engine(database_url: str):
    return create_async_engine(database_url, **_engine_kwargs(database_url))


engine = _create_engine(settings.DATABASE_URL)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


def configure_database(database_url: str) -> None:
    global engine, AsyncSessionLocal
    engine = _create_engine(database_url)
    AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
