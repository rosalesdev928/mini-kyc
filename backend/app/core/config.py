"""Application settings, loaded from environment variables (never hardcoded)."""

from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", populate_by_name=True)

    # --- Database (DB_* names, with Railway's MYSQL* names as fallback) ---
    db_host: str = Field("localhost", validation_alias=AliasChoices("DB_HOST", "MYSQLHOST"))
    db_port: int = Field(3306, validation_alias=AliasChoices("DB_PORT", "MYSQLPORT"))
    db_user: str = Field("root", validation_alias=AliasChoices("DB_USER", "MYSQLUSER"))
    db_password: str = Field("", validation_alias=AliasChoices("DB_PASSWORD", "MYSQLPASSWORD"))
    db_name: str = Field("mini_kyc", validation_alias=AliasChoices("DB_NAME", "MYSQLDATABASE"))
    db_pool_size: int = 5
    auto_migrate: bool = True

    # --- OCR / AI ---
    ocr_provider: str = "gemini"  # "gemini" or "mock" (mock is for local demos and tests only)
    gemini_api_key: str = ""
    gemini_model: str = "gemini-flash-latest"
    gemini_fallback_model: str = "gemini-3.6-flash"  # used when the primary model keeps failing; "" disables it
    gemini_timeout_seconds: int = 40  # per attempt
    gemini_max_attempts: int = 3  # per model, for transient errors (429/5xx/timeouts)
    gemini_retry_base_seconds: float = 1.0  # exponential backoff: 1s, 2s, 4s...
    gemini_total_budget_seconds: float = 80.0  # no new attempt starts after this (hosting request limit)
    min_verified_confidence: float = 0.85
    duplicate_check_enabled: bool = True  # flag the same document/photo registered under another email

    # --- Operator review and admin dashboard (same shared secret) ---
    review_api_key: str = ""  # empty = review and admin endpoints are disabled (secure by default)

    # --- Privacy and abuse protection ---
    data_retention_days: int = 30  # records older than this are anonymized automatically; 0 = keep forever
    retention_check_hours: float = 6.0  # how often the retention job runs while the server is awake
    rate_limit_uploads_per_minute: int = 10  # per IP; also protects the free AI quota. 0 = no limit
    rate_limit_history_per_minute: int = 30  # per IP, for the public history lookup. 0 = no limit
    rate_limit_admin_failures: int = 5  # wrong operator keys allowed per IP in the window below. 0 = no limit
    rate_limit_admin_window_seconds: int = 300
    security_headers_enabled: bool = True

    # --- Upload validation ---
    max_upload_bytes: int = 5 * 1024 * 1024
    min_image_side_px: int = 300
    blur_threshold: float = 25.0

    # --- Web ---
    cors_origins: str = ""  # comma separated, empty = same-origin only
    static_dir: str = ""  # built frontend; served by the API in production
    database_dir: str = str(BACKEND_ROOT.parent / "database")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
