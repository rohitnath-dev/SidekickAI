 ## BaseSettings loads settings from the .env file.
# SettingsConfigDict configures how those settings are loaded.
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):

    PROJECT_NAME: str = "Sidekick AI Backend"
    VERSION: str = "1.0.0"

    DESCRIPTION: str = (
        "An AI-powered chief of staff that prioritizes messages, "
        "generates smart replies, remembers context, and helps users "
        "stay organized."
    )

    DEBUG: bool = True


    HOST: str = "127.0.0.1"
    PORT: int = 8000

  # Used to create and verify user login tokens.

    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    DATABASE_URL: str


    OPENROUTER_API_KEY: str

    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    MODEL_NAME: str = "openai/gpt-4.1-mini"

    TEMPERATURE: float = 0.4

    MAX_TOKENS: int = 2048

    HTTP_REFERER: str = "http://localhost:3000"

    APP_TITLE: str = "Sidekick AI"

  # Used for Google Login and Gmail access.

    GOOGLE_CLIENT_ID: str
    GOOGLE_CLIENT_SECRET: str
    GOOGLE_REDIRECT_URI: str


    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
    ]


    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()