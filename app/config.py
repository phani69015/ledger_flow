from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    APP_NAME: str = "LedgerFlow"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "sqlite:///./ledgerflow.db"

    # JWT Auth
    SECRET_KEY: str = "dev-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours


@lru_cache()
def get_settings() -> Settings:
    """Cached settings instance."""
    return Settings()
