"""Application configuration for VaultDocs."""

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
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
