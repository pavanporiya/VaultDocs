"""Application configuration for VaultDocs."""

from functools import lru_cache

from pydantic import Field
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
    )

    postgres_port: int = Field(
        default=5432,
        description="PostgreSQL port.",
    )

    postgres_db: str = Field(
        default="vaultdocs",
        description="Database name.",
    )

    postgres_user: str = Field(
        default="vaultdocs",
        description="Database username.",
    )

    postgres_password: str = Field(
        default="vaultdocs_dev_password",
        description="Database password.",
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
    # Computed Properties
    # -------------------------------------------------------------------------

    @property
    def database_url(self) -> str:
        """Return the SQLAlchemy database URL."""

        return (
            f"postgresql+asyncpg://"
            f"{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}"
            f"/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance."""
    return Settings()


settings = get_settings()
