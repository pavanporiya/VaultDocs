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
