"""
Sidekick AI — Application Configuration

All settings are loaded from environment variables / .env file.
No secrets are hardcoded here.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):

    # ------------------------------------------------------------------ #
    # Project                                                               #
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
    # Server                                                                #
    # ------------------------------------------------------------------ #
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # ------------------------------------------------------------------ #
    # Security / JWT                                                        #
    # ------------------------------------------------------------------ #
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # ------------------------------------------------------------------ #
    # Database                                                              #
    # ------------------------------------------------------------------ #
    DATABASE_URL: str = "sqlite:///./sidekick.db"

    # ------------------------------------------------------------------ #
    # OpenRouter LLM                                                        #
    # ------------------------------------------------------------------ #
    OPENROUTER_API_KEY: str
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL: str = "openai/gpt-4.1-mini"
    OPENROUTER_TIMEOUT: float = 60.0
    OPENROUTER_TEMPERATURE: float = 0.4
    OPENROUTER_MAX_TOKENS: int = 2048
    HTTP_REFERER: str = "https://sidekick.ai"
    APP_TITLE: str = "Sidekick AI"

    # ------------------------------------------------------------------ #
    # Google OAuth                                                          #
    # ------------------------------------------------------------------ #
    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/api/v1/gmail/callback"

    # ------------------------------------------------------------------ #
    # LinkedIn OAuth                                                        #
    # ------------------------------------------------------------------ #
    LINKEDIN_CLIENT_ID: str
    LINKEDIN_CLIENT_SECRET: str
    LINKEDIN_REDIRECT_URI: str = "http://localhost:8000/api/v1/linkedin/callback"

    # ------------------------------------------------------------------ #
    # Twitter / X                                                           #
    # ------------------------------------------------------------------ #
    TWITTER_API_KEY: str = ""
    TWITTER_API_SECRET: str = ""
    TWITTER_BEARER_TOKEN: str = ""
    TWITTER_ACCESS_TOKEN: str = ""
    TWITTER_ACCESS_SECRET: str = ""
    TWITTER_USER_ID: str = ""

    # ------------------------------------------------------------------ #
    # WhatsApp (Meta Cloud API)                                             #
    # ------------------------------------------------------------------ #
    WHATSAPP_API_TOKEN: str = ""
    WHATSAPP_PHONE_NUMBER_ID: str = ""
    WHATSAPP_VERIFY_TOKEN: str = ""
    WHATSAPP_APP_SECRET: str = ""
    WHATSAPP_API_BASE_URL: str = "https://graph.facebook.com/v19.0"
    META_APP_ID: str = ""
    META_APP_SECRET: str = ""
    WHATSAPP_CONFIG_ID: str = ""
    WHATSAPP_REDIRECT_URI: str = "http://localhost:8000/api/v1/whatsapp/callback"

    # ------------------------------------------------------------------ #
    # Telegram                                                              #
    # ------------------------------------------------------------------ #
    TELEGRAM_API_ID: int = 123456
    TELEGRAM_API_HASH: str = "mock_api_hash_value"
    TELEGRAM_SESSION_ENCRYPTION_KEY: str = ""

    # ------------------------------------------------------------------ #
    # CORS                                                                  #
    # ------------------------------------------------------------------ #
    ALLOWED_ORIGINS: list[str] = ["*"]

    # ------------------------------------------------------------------ #
    # Pydantic config                                                       #
    # ------------------------------------------------------------------ #
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
