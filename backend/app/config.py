from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    secret_key: str
    access_token_expire_minutes: int = 480
    environment: str = "development"
    # Comma-separated allowed CORS origins -- defaults to the Vite dev
    # server so local dev needs no .env change; production sets its own
    # via the CORS_ORIGINS env var (never a code change per environment).
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    # P.1: "file storage local volume -> S3." Phase 1 = local disk; a
    # future S3 migration only needs to change how attachments.py reads/
    # writes bytes, not this setting's meaning.
    attachment_storage_root: str = "uploads"


settings = Settings()
