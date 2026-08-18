"""
Sidekick AI — Application Configuration

All settings are loaded from environment variables / .env file.
No secrets are hardcoded here.
"""

from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    # ------------------------------------------------------------------ #
    # Project
    # ------------------------------------------------------------------ #
    PROJECT_NAME: str = "Sidekick AI"
    VERSION: str = "1.0.0"
    DESCRIPTION: str = (
        "An AI-powered executive assistant that prioritises messages, "
        "generates smart replies, remembers context, and helps users "
        "stay organised across Gmail, Calendar, WhatsApp, X and more."
    )
    DEBUG: bool = False

    # ------------------------------------------------------------------ #
    # Server
    # ------------------------------------------------------------------ #
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ------------------------------------------------------------------ #
    # Security / JWT
    # ------------------------------------------------------------------ #
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    COOKIE_SECURE: bool = True
    COOKIE_SAMESITE: str = "lax"

    # ------------------------------------------------------------------ #
    # Database
    # ------------------------------------------------------------------ #
    DATABASE_URL: str = "sqlite:///./sidekick.db"

    # ------------------------------------------------------------------ #
    # LLM Configuration
    #
    # Supported providers:
    #   - ollama
    #   - openrouter
    #
    # The provider can later be overridden by a user's request/config.
    # ------------------------------------------------------------------ #

    # Default provider
    LLM_PROVIDER: str = "openrouter"

    # ------------------------------------------------------------------ #
    # Ollama
    # ------------------------------------------------------------------ #

    # Default local Ollama server.
    OLLAMA_BASE_URL: str = "http://localhost:11434"

    # Default Ollama model.
    OLLAMA_MODEL: str = "llama3.2"

    # ------------------------------------------------------------------ #
    # OpenRouter
    # ------------------------------------------------------------------ #

    OPENROUTER_API_KEY: Optional[str] = None

    OPENROUTER_BASE_URL: str = (
        "https://openrouter.ai/api/v1"
    )

    # Default model.
    # This can later be overridden by the user's selected model.
    OPENROUTER_MODEL: str = "openrouter/free"

    OPENROUTER_TIMEOUT: float = 60.0
    OPENROUTER_TEMPERATURE: float = 0.4
    OPENROUTER_MAX_TOKENS: int = 2048

    # OpenRouter optional metadata
    HTTP_REFERER: str = "https://sidekick.ai"
    APP_TITLE: str = "Sidekick AI"

    # ------------------------------------------------------------------ #
    # Background Ingestion Poller
    # ------------------------------------------------------------------ #
    POLLER_INTERVAL_SECONDS: int = 3600
    POLLER_ENABLED: bool = False

    # ------------------------------------------------------------------ #
    # Google OAuth
    # ------------------------------------------------------------------ #
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str = (
        "http://localhost:8000/api/v1/gmail/callback"
    )



    # ------------------------------------------------------------------ #
    # Twitter / X OAuth 2.0
    # ------------------------------------------------------------------ #
    TWITTER_CLIENT_ID: str = ""
    TWITTER_CLIENT_SECRET: str = ""
    TWITTER_REDIRECT_URI: str = (
        "http://localhost:8000/api/v1/twitter/callback"
    )
    TWITTER_APP_SECRET: str = ""

    # ------------------------------------------------------------------ #
    # Twitter / X Legacy
    # ------------------------------------------------------------------ #
    TWITTER_API_KEY: str = ""
    TWITTER_API_SECRET: str = ""
    TWITTER_BEARER_TOKEN: str = ""
    TWITTER_ACCESS_TOKEN: str = ""
    TWITTER_ACCESS_SECRET: str = ""
    TWITTER_USER_ID: str = ""


    # ------------------------------------------------------------------ #
    # Telegram
    # ------------------------------------------------------------------ #
    TELEGRAM_API_ID: int = 123456
    TELEGRAM_API_HASH: str = "mock_api_hash_value"
    TELEGRAM_SESSION_ENCRYPTION_KEY: str = ""


    # ------------------------------------------------------------------ #
    # CORS
    # ------------------------------------------------------------------ #
    ALLOWED_ORIGINS: list[str] = ["*"]

    from pydantic import model_validator

    @model_validator(mode="after")
    def fix_postgres_url(self) -> "Settings":
        if self.DATABASE_URL and self.DATABASE_URL.startswith("postgres://"):
            self.DATABASE_URL = self.DATABASE_URL.replace("postgres://", "postgresql://", 1)
        return self

    # ------------------------------------------------------------------ #
    # Pydantic config
    # ------------------------------------------------------------------ #
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()