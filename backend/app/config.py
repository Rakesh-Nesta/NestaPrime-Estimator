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

    # Amendment 8 (Section 8): the company's self-hosted WhatsApp backend
    # (wa-gateway -- Baileys/WhatsApp Web protocol, not a paid BSP).
    # Blank by default so a dev/test environment with no .env entry for
    # these simply can't reach a real gateway -- app/services/wa_gateway.py
    # treats an empty base URL as "not configured" and fails fast rather
    # than attempting a network call.
    wa_gateway_base_url: str = ""
    wa_gateway_api_key: str = ""
    # Verified against wa-gateway's X-Webhook-Secret header on inbound
    # delivery-status webhooks (app/api/wa_gateway_webhook.py).
    wa_gateway_webhook_secret: str = ""

    # Amendment 8 (Section 8): Telegram Bot API token (from @BotFather).
    # Same "blank = not configured, fail fast" discipline as wa-gateway.
    telegram_bot_token: str = ""


settings = Settings()
