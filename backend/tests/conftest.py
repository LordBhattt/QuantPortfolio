from __future__ import annotations

from pathlib import Path
import sys
import uuid

import pytest

pytest_asyncio = pytest.importorskip("pytest_asyncio")
pytest.importorskip("sqlalchemy")

CURRENT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = CURRENT_DIR.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.database import metadata
from backend.models import asset as asset_model  # noqa: F401  # ensure table registration
from backend.models import holding as holding_model  # noqa: F401  # ensure table registration
from backend.models import investor_profile as investor_profile_model  # noqa: F401  # ensure table registration
from backend.models import portfolio as portfolio_model  # noqa: F401  # ensure table registration
from backend.models import portfolio_alert as portfolio_alert_model  # noqa: F401  # ensure table registration
from backend.models import user as user_model  # noqa: F401  # ensure table registration


@pytest.fixture
def sample_user_id() -> uuid.UUID:
    return uuid.uuid4()


@pytest.fixture
def sqlite_database_url(tmp_path_factory: pytest.TempPathFactory) -> str:
    database_path = tmp_path_factory.mktemp("db") / "quantportfolio-test.db"
    return f"sqlite+aiosqlite:///{database_path.as_posix()}"


@pytest_asyncio.fixture
async def sqlite_session_factory(sqlite_database_url: str):
    engine = create_async_engine(sqlite_database_url, future=True)
    async with engine.begin() as connection:
        await connection.run_sync(metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        yield session_factory
    finally:
        await engine.dispose()
