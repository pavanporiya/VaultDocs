"""
Health check endpoints for VaultDocs.
"""

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from vaultdocs.core.settings import settings
from vaultdocs.db.dependencies import get_database_session

router = APIRouter(
    prefix="/health",
    tags=["Health"],
)


@router.get("")
async def health_check(
    db: AsyncSession = Depends(get_database_session),
) -> dict[str, str]:
    """
    Verify application and database health.
    """

    await db.execute(text("SELECT 1"))

    return {
        "status": "healthy",
        "database": "connected",
        "environment": settings.app_environment,
        "version": settings.app_version,
    }
