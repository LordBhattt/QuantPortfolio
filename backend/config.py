from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=("backend/.env", ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    APP_NAME: str = "QuantPortfolio"
    DEBUG: bool = False
    SECRET_KEY: str = "change-me-to-a-long-random-secret"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    API_V1_PREFIX: str = "/api/v1"
    ALLOWED_ORIGINS: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # DB
    DATABASE_URL: str = "postgresql+asyncpg://postgres:password@localhost:5432/quantportfolio"

    # Redis
    REDIS_URL: str = "redis://localhost:6379"

    # External APIs
    ALPHA_VANTAGE_KEY: str = "demo"
    COINGECKO_BASE: str = "https://api.coingecko.com/api/v3"
    YAHOO_BASE: str = "https://query1.finance.yahoo.com/v8/finance"
    AMFI_NAV_URL: str = "https://www.amfiindia.com/spages/NAVAll.txt"

    # ML
    LSTM_WEIGHTS_PATH: str = "ml/weights/lstm_latest.pt"
    LSTM_LOOKBACK_DAYS: int = 60
    LSTM_FORECAST_DAYS: int = 30

    # Quant params
    RISK_FREE_RATE: float = 0.065
    MVO_ROLLING_WINDOW_DAYS: int = 252
    HMM_N_STATES: int = 3
    MONTE_CARLO_PATHS: int = 1000
    MONTE_CARLO_HORIZON_DAYS: int = 252
    CVAR_CONFIDENCE: float = 0.95

    @field_validator("DEBUG", mode="before")
    @classmethod
    def normalize_debug(cls, value: object) -> bool | object:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"1", "true", "yes", "on", "debug", "development", "dev"}:
                return True
            if normalized in {"0", "false", "no", "off", "release", "prod", "production"}:
                return False
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
