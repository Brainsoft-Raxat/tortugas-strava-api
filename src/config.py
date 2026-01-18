from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # APP
    APP_NAME: str = "Tortugas"
    ENVIRONMENT: Literal["local", "staging", "production"] = "local"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"  # DEBUG, INFO, WARNING, ERROR, CRITICAL

    # DB
    DATABASE_URL: str

    # REDIS
    REDIS_URL: str = "fakeredisurl"

    # Strava OAuth
    STRAVA_CLIENT_ID: str
    STRAVA_CLIENT_SECRET: str
    STRAVA_REDIRECT_URI: str
    STRAVA_VERIFY_TOKEN: str
    STRAVA_CLUB_ID: int

    # Webhooks (optional - only needed for webhook functionality)
    WEBHOOK_BASE_URL: str | None = None

    # CORS
    CORS_ORIGINS: list[str] = ["*"]

    # Security
    ADMIN_API_KEY: str

    @property
    def webhook_callback_url(self) -> str | None:
        """Get full webhook callback URL if configured."""
        if self.WEBHOOK_BASE_URL:
            return f"{self.WEBHOOK_BASE_URL}/webhooks/strava"
        return None

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra fields (like POSTGRES_* used by docker-compose)


@lru_cache()
def get_settings() -> Settings:
    """Cached settings only loads once"""
    return Settings()
