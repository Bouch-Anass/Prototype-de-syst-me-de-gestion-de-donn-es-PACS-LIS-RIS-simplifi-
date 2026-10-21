"""Configuration minimale, validée avant de servir des requêtes."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    database_url: str
    app_origin: str
    cookie_secure: bool
    hl7_service_secret: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        database_url = os.getenv("DATABASE_URL", "")
        app_env = os.getenv("APP_ENV", "development")
        app_origin = os.getenv("APP_ORIGIN", "http://127.0.0.1:8000").rstrip("/")
        if app_env not in {"development", "production", "test"}:
            raise ValueError("APP_ENV must be development, production or test")
        if not database_url.startswith("postgresql+psycopg://") and not (
            app_env == "test" and database_url.startswith("sqlite+pysqlite://")
        ):
            raise ValueError("DATABASE_URL must use postgresql+psycopg (SQLite is test-only)")
        if app_env == "production" and not app_origin.startswith("https://"):
            raise ValueError("APP_ORIGIN must use HTTPS in production")
        if not app_origin.startswith(("http://", "https://")):
            raise ValueError("APP_ORIGIN must be an HTTP(S) origin")
        hl7_service_secret = os.getenv("HL7_SERVICE_SECRET") or None
        if app_env == "production" and hl7_service_secret and len(hl7_service_secret) < 32:
            raise ValueError("HL7_SERVICE_SECRET must be at least 32 characters in production")
        return cls(database_url, app_origin, app_env == "production", hl7_service_secret)
