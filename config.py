"""
Central configuration for the Sidekick AI backend.
Loads all environment variables from the .env file.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # --------------------------------------------------
    # Project Information
    # --------------------------------------------------

    PROJECT_NAME: str = "Sidekick AI Backend"
    VERSION: str = "1.0.0"

    DESCRIPTION: str = (
        "An AI-powered chief of staff that prioritizes messages, "
        "generates smart replies, remembers context, and helps users "
        "stay organized."
    )

    DEBUG: bool = True

    # --------------------------------------------------
    # Server
    # --------------------------------------------------

    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # --------------------------------------------------
    # Security
    # --------------------------------------------------

    SECRET_KEY: str

    JWT_ALGORITHM: str = "HS256"

    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # --------------------------------------------------
    # Database
    # --------------------------------------------------

    DATABASE_URL: str

    # --------------------------------------------------
    # Mesh AI
    # --------------------------------------------------

    MESH_API_KEY: str

    MESH_BASE_URL: str

    MODEL_NAME: str = "mesh-chat"

    TEMPERATURE: float = 0.4

    MAX_TOKENS: int = 2048

    # --------------------------------------------------
    # Google OAuth
    # --------------------------------------------------

    GOOGLE_CLIENT_ID: str

    GOOGLE_CLIENT_SECRET: str

    GOOGLE_REDIRECT_URI: str

    # --------------------------------------------------
    # Embeddings
    # --------------------------------------------------

    EMBEDDING_MODEL: str = "text-embedding-3-small"

    # --------------------------------------------------
    # CORS
    # --------------------------------------------------

    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
    ]

    # --------------------------------------------------
    # Environment Configuration
    # --------------------------------------------------

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"
    )


settings = Settings()
