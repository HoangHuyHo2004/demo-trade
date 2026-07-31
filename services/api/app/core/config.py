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

    # Shared with the web app's Auth.js instance. Sessions are HS256-signed
    # JWTs issued by Auth.js and validated here. Must be at least 32 bytes
    # in production. In demo/dev it defaults to api_secret_key.
    auth_secret_key: str = ""
    # Cookie name Auth.js writes on the browser and the API reads. Kept
    # configurable so operators can rebrand.
    auth_cookie_name: str = "demo-trade.session"
    # Max session TTL, seconds. Enforced by the JWT `exp` claim on issue,
    # cross-checked here on verify.
    auth_session_max_age_s: int = 7 * 24 * 3600

    database_url: str = "postgresql+asyncpg://demotrade:demotrade@localhost:5432/demotrade"
    alembic_database_url: str = "postgresql://demotrade:demotrade@localhost:5432/demotrade"
    redis_url: str = "redis://localhost:6379/0"

    llm_provider: str = "mock"
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # --- Provider configuration ---
    # When true, keep DEMO_MODE registry (mock only). When false, the
    # registry auto-selects real adapters where credentials are present.
    # When true, the registry skips ALL real adapters and routes every
    # market to the deterministic mock provider. Used by the test suite
    # (and available as an escape hatch in production).
    use_mock_providers_only: bool = False
    # When true, POST /backtests runs the job inline in the request
    # thread rather than enqueueing it via Celery. Used by tests and by
    # single-node demo installs without a Redis broker.
    use_sync_jobs: bool = False
    coinbase_api_url: str = "https://api.exchange.coinbase.com"
    alpaca_api_key: str = ""
    alpaca_api_secret: str = ""
    alpaca_api_url: str = "https://data.alpaca.markets"
    ssi_fc_consumer_id: str = ""
    ssi_fc_consumer_secret: str = ""
    ssi_fc_api_url: str = "https://fc-data.ssi.com.vn"

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]

    @property
    def effective_auth_secret(self) -> str:
        """AUTH_SECRET or, as a dev convenience, API_SECRET_KEY."""
        return self.auth_secret_key or self.api_secret_key


@lru_cache
def get_settings() -> Settings:
    return Settings()
