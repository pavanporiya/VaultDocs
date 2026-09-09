"""
Database dependency providers for VaultDocs.
"""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from vaultdocs.db.session import AsyncSessionLocal


async def get_database_session() -> AsyncGenerator[AsyncSession]:
    """
    Provide a database session dependency.
    """

    async with AsyncSessionLocal() as session:
        yield session
