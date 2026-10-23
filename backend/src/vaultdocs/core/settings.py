"""Application configuration for VaultDocs."""

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # -------------------------------------------------------------------------
    # Application Settings
    # -------------------------------------------------------------------------

    app_name: str = Field(
        default="VaultDocs API",
        description="Application name.",
    )

    app_version: str = Field(
        default="0.1.0",
        description="Application version.",
    )

    app_environment: str = Field(
        default="development",
        description="Application environment.",
    )

    debug: bool = Field(
        default=True,
        description="Enable debug mode.",
    )

    # -------------------------------------------------------------------------
    # Database Settings
    # -------------------------------------------------------------------------

    postgres_host: str = Field(
        default="localhost",
        description="PostgreSQL host.",
        validation_alias=AliasChoices("postgres_host", "database_host"),
    )

    postgres_port: int = Field(
        default=5432,
        description="PostgreSQL port.",
        validation_alias=AliasChoices("postgres_port", "database_port"),
    )

    postgres_db: str = Field(
        default="vaultdocs",
        description="Database name.",
        validation_alias=AliasChoices("postgres_db", "database_name"),
    )

    postgres_user: str = Field(
        default="vaultdocs",
        description="Database username.",
        validation_alias=AliasChoices("postgres_user", "database_user"),
    )

    postgres_password: str = Field(
        default="vaultdocs_dev_password",
        description="Database password.",
        validation_alias=AliasChoices("postgres_password", "database_password"),
    )

    # -------------------------------------------------------------------------
    # Security Settings
    # -------------------------------------------------------------------------

    secret_key: str = Field(
        default="replace-me-in-production",
        description="JWT secret key.",
    )

    algorithm: str = Field(
        default="HS256",
        description="JWT signing algorithm.",
    )

    access_token_expire_minutes: int = Field(
        default=30,
        description="Access token expiry in minutes.",
    )

    # -------------------------------------------------------------------------
    # Email & Verification Settings (Gmail SMTP / OTP)
    # -------------------------------------------------------------------------

    smtp_host: str = Field(
        default="smtp.gmail.com",
        description="SMTP server hostname.",
        validation_alias=AliasChoices("smtp_host", "mail_host"),
    )

    smtp_port: int = Field(
        default=587,
        description="SMTP server port.",
        validation_alias=AliasChoices("smtp_port", "mail_port"),
    )

    smtp_username: str | None = Field(
        default=None,
        description="SMTP username / Gmail address. Never hardcoded.",
        validation_alias=AliasChoices("smtp_username", "smtp_user", "mail_username"),
    )

    smtp_password: str | None = Field(
        default=None,
        description="SMTP password / Gmail App Password. Never hardcoded or logged.",
        validation_alias=AliasChoices("smtp_password", "smtp_pass", "mail_password"),
    )

    smtp_from_email: str | None = Field(
        default=None,
        description="Sender email address.",
        validation_alias=AliasChoices("smtp_from_email", "mail_from"),
    )

    smtp_from_name: str = Field(
        default="VaultDocs",
        description="Sender display name.",
        validation_alias=AliasChoices("smtp_from_name", "mail_from_name"),
    )

    smtp_use_tls: bool = Field(
        default=True,
        description="Enable STARTTLS for SMTP.",
        validation_alias=AliasChoices("smtp_use_tls", "smtp_tls", "mail_tls"),
    )

    smtp_timeout_seconds: float = Field(
        default=10.0,
        gt=0,
        description="SMTP connection timeout in seconds.",
        validation_alias=AliasChoices("smtp_timeout_seconds", "smtp_timeout"),
    )

    otp_expire_minutes: int = Field(
        default=10,
        ge=1,
        le=60,
        description="OTP validity period in minutes.",
        validation_alias=AliasChoices("otp_expire_minutes", "otp_expiry_minutes"),
    )

    otp_resend_cooldown_seconds: int = Field(
        default=60,
        ge=0,
        le=600,
        description="Minimum seconds required between OTP resend attempts.",
        validation_alias=AliasChoices("otp_resend_cooldown_seconds", "otp_cooldown_seconds"),
    )

    otp_max_failed_attempts: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum failed OTP verification attempts before code invalidation.",
        validation_alias=AliasChoices("otp_max_failed_attempts", "otp_max_attempts"),
    )

    password_reset_expire_minutes: int = Field(
        default=15,
        ge=1,
        le=120,
        description="Password reset token validity period in minutes.",
        validation_alias=AliasChoices(
            "password_reset_expire_minutes",
            "reset_token_expire_minutes",
        ),
    )

    password_reset_resend_cooldown_seconds: int = Field(
        default=60,
        ge=0,
        le=600,
        description="Minimum seconds required between password reset requests.",
        validation_alias=AliasChoices(
            "password_reset_resend_cooldown_seconds",
            "reset_cooldown_seconds",
        ),
    )

    password_reset_max_failed_attempts: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum failed reset token verification attempts before invalidation.",
        validation_alias=AliasChoices(
            "password_reset_max_failed_attempts",
            "reset_max_attempts",
        ),
    )

    frontend_url: str = Field(
        default="http://localhost:5173",
        description="Frontend base URL for links in emails.",
        validation_alias=AliasChoices("frontend_url", "app_url", "client_url"),
    )

    # -------------------------------------------------------------------------
    # Storage Settings
    # -------------------------------------------------------------------------

    storage_dir: str = Field(
        default="var/storage",
        description="Path to local storage directory for uploaded files.",
    )

    max_upload_size: int = Field(
        default=10 * 1024 * 1024,
        description="Maximum allowed file upload size in bytes.",
    )

    custom_database_url: str | None = Field(
        default=None,
        description="Optional database URL override.",
        validation_alias=AliasChoices("database_url", "custom_database_url"),
    )

    # -------------------------------------------------------------------------
    # Document Intelligence Settings
    # -------------------------------------------------------------------------

    max_extracted_chars: int = Field(
        default=200_000,
        ge=1_000,
        description="Maximum characters of extracted text persisted per document.",
    )

    intelligence_chunk_chars: int = Field(
        default=900,
        ge=200,
        description="Target chunk size (characters) for content search.",
    )

    intelligence_chunk_overlap: int = Field(
        default=150,
        ge=0,
        description="Overlap (characters) between consecutive content chunks.",
    )

    ai_provider: str = Field(
        default="extractive",
        description=(
            "Summary provider: 'extractive' (local, no credentials, default) or "
            "'openai_compatible' (HTTP chat completions API)."
        ),
    )

    ai_base_url: str = Field(
        default="https://api.openai.com/v1",
        description="Base URL for the openai_compatible summary provider.",
    )

    ai_model: str = Field(
        default="gpt-4o-mini",
        description="Model name for the openai_compatible summary provider.",
    )

    ai_api_key: str | None = Field(
        default=None,
        description="API key for the AI provider. Read from the environment; never logged.",
    )

    ai_timeout_seconds: float = Field(
        default=30.0,
        gt=0,
        description="Timeout for AI provider HTTP requests.",
    )


    ai_max_input_chars: int = Field(
        default=6_000,
        ge=500,
        description="Maximum characters of document text sent to an AI provider.",
    )

    # -------------------------------------------------------------------------
    # Device Approval / Web Push / Trusted Device Settings
    # -------------------------------------------------------------------------

    vapid_public_key: str | None = Field(
        default=None,
        description=(
            "VAPID public key (base64url, uncompressed P-256 point, 65 bytes). "
            "Required for Web Push sign-in approvals."
        ),
        validation_alias=AliasChoices("vapid_public_key", "VAPID_PUBLIC_KEY"),
    )

    vapid_private_key: str | None = Field(
        default=None,
        description=(
            "VAPID private key (base64url). Required for Web Push sign-in approvals. "
            "Never logged. Generate with: py_vapid generate --applicationServerKey"
        ),
        validation_alias=AliasChoices("vapid_private_key", "VAPID_PRIVATE_KEY"),
    )

    vapid_claims_email: str = Field(
        default="admin@vaultdocs.local",
        description="VAPID subject contact email (mailto: claim).",
        validation_alias=AliasChoices("vapid_claims_email", "VAPID_CLAIMS_EMAIL"),
    )

    login_challenge_expire_seconds: int = Field(
        default=300,
        ge=30,
        le=1800,
        description="Lifetime of a pending sign-in approval challenge (seconds).",
    )

    trusted_device_expire_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="How long a trusted device (Remember this device) stays valid.",
    )

    push_subscription_expire_days: int = Field(
        default=60,
        ge=1,
        le=365,
        description="Lifetime of a stored Web Push subscription before forced rotation.",
    )

    login_approval_code_expire_minutes: int = Field(
        default=10,
        ge=1,
        le=60,
        description="Lifetime of the email fallback sign-in approval code.",
    )

    login_approval_code_max_failed_attempts: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Max failed email approval-code attempts before code invalidation.",
    )

    login_approval_code_cooldown_seconds: int = Field(
        default=60,
        ge=0,
        le=600,
        description="Minimum seconds between email approval-code resends.",
    )

    rate_limit_enabled: bool = Field(
        default=True,
        description="Enable in-process sliding-window rate limiting for auth endpoints.",
    )

    rate_limit_login_attempts: int = Field(
        default=10,
        ge=1,
        description="Max login attempts per identity/IP within the login window.",
    )

    rate_limit_login_window_seconds: int = Field(
        default=300,
        ge=10,
        description="Sliding window (seconds) for login rate limiting.",
    )

    rate_limit_challenge_attempts: int = Field(
        default=5,
        ge=1,
        description="Max approval challenges that may be created per email within the window.",
    )

    rate_limit_poll_attempts: int = Field(
        default=60,
        ge=1,
        description="Max challenge status polls per challenge within the poll window.",
    )

    rate_limit_poll_window_seconds: int = Field(
        default=60,
        ge=10,
        description="Sliding window (seconds) for challenge status polling.",
    )

    rate_limit_approve_attempts: int = Field(
        default=20,
        ge=1,
        description="Max approval/deny attempts per user within the approve window.",
    )

    rate_limit_resend_attempts: int = Field(
        default=5,
        ge=1,
        description="Max challenge resend requests per challenge within the resend window.",
    )

    rate_limit_resend_window_seconds: int = Field(
        default=600,
        ge=10,
        description="Sliding window (seconds) for challenge resends.",
    )

    # -------------------------------------------------------------------------
    # VAPID Configuration Validation
    # -------------------------------------------------------------------------

    def validate_push_configuration(self) -> None:
        """
        Validate Web Push (VAPID) configuration integrity.

        Raises RuntimeError when configuration is partially set or malformed so
        the application fails safely at startup instead of silently issuing
        broken or insecure push notifications. When both keys are absent the
        push channel is simply disabled (email approval fallback still applies).
        """
        public_key = (self.vapid_public_key or "").strip()
        private_key = (self.vapid_private_key or "").strip()

        if not public_key and not private_key:
            return  # Push disabled; email approval fallback covers sign-in.

        if not public_key or not private_key:
            raise RuntimeError(
                "INVALID PUSH CONFIGURATION: Both VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY "
                "must be set together, or both left empty to disable Web Push. "
                "Failing safely at startup."
            )

        import base64

        def _b64url_decode(value: str) -> bytes:
            padding = "=" * (-len(value) % 4)
            return base64.urlsafe_b64decode(value + padding)

        try:
            public_bytes = _b64url_decode(public_key)
        except Exception as exc:
            raise RuntimeError(
                "INVALID PUSH CONFIGURATION: VAPID_PUBLIC_KEY is not valid base64url data."
            ) from exc

        if len(public_bytes) != 65 or public_bytes[0] != 0x04:
            raise RuntimeError(
                "INVALID PUSH CONFIGURATION: VAPID_PUBLIC_KEY must be a 65-byte "
                "uncompressed P-256 point (base64url)."
            )

        try:
            private_bytes = _b64url_decode(private_key)
        except Exception as exc:
            raise RuntimeError(
                "INVALID PUSH CONFIGURATION: VAPID_PRIVATE_KEY is not valid base64url data."
            ) from exc

        if len(private_bytes) not in (27, 28, 32):
            raise RuntimeError(
                "INVALID PUSH CONFIGURATION: VAPID_PRIVATE_KEY must be the base64url "
                "encoding of a P-256 private key (27/28-byte DER or 32-byte raw)."
            )

    # -------------------------------------------------------------------------
    # Database URLs
    # -------------------------------------------------------------------------

    @property
    def database_url(self) -> str:
        """
        Async SQLAlchemy database URL.
        Used by the FastAPI application.
        """
        if self.custom_database_url:
            return self.custom_database_url

        return (
            f"postgresql+asyncpg://"
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}"
            f"/{self.postgres_db}"
        )

    @property
    def alembic_database_url(self) -> str:
        """
        Sync database URL.
        Used only by Alembic migrations.
        """
        if self.custom_database_url:
            url = self.custom_database_url
            if url.startswith("postgresql+asyncpg://"):
                return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
            if url.startswith("sqlite+aiosqlite://"):
                return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
            return url

        return (
            f"postgresql+psycopg://"
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}"
            f"/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()
