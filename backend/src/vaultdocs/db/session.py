"""
Database session configuration for VaultDocs.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from vaultdocs.core.settings import settings

# =============================================================================
# Database Engine
# =============================================================================

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    future=True,
)

# =============================================================================
# Session Factory
# =============================================================================

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
)

# =============================================================================
# Database Dependency
# =============================================================================


async def get_db() -> AsyncGenerator[AsyncSession]:
    """
    Provide a database session.
    """

    async with AsyncSessionLocal() as session:
        yield session
