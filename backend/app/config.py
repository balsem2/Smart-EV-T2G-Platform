from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Application settings loaded from backend/.env."""

    app_name: str = "Smart EV API"
    app_env: str = "development"
    database_url: str | None = None
    jwt_secret: str = "change-me"
    access_token_expire_minutes: int = 1440
    station_api_key: str = "change-station-key"

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
