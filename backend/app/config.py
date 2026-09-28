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
    econtrol_api_key: str | None = None
    econtrol_referer: str | None = None
    frontend_url: str = "http://smart-ev.localhost:5173"
    stripe_secret_key: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_from_email: str = "no-reply@smart-ev.at"
    smtp_use_tls: bool = True

    model_config = SettingsConfigDict(
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
