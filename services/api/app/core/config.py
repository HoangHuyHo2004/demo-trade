"""App configuration loaded from env vars (Pydantic Settings)."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    app_env: str = "development"
    demo_mode: bool = True
    log_level: str = "INFO"

    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_cors_origins: str = "http://localhost:3000"
    api_secret_key: str = Field(default="dev-only-change-me-32chars-min-xxxxxxxxxx", min_length=32)
    api_demo_user_email: str = "demo@demo-trade.local"

    database_url: str = "postgresql+asyncpg://demotrade:demotrade@localhost:5432/demotrade"
    alembic_database_url: str = "postgresql://demotrade:demotrade@localhost:5432/demotrade"
    redis_url: str = "redis://localhost:6379/0"

    llm_provider: str = "mock"
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
