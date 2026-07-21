"""
Version 1 API router.
"""

from fastapi import APIRouter

from vaultdocs.api.v1.auth import router as auth_router
from vaultdocs.api.v1.documents import router as documents_router
from vaultdocs.api.v1.folders import router as folders_router
from vaultdocs.api.v1.health import router as health_router
from vaultdocs.api.v1.users import router as users_router

router = APIRouter(prefix="/v1")

router.include_router(health_router)
router.include_router(auth_router)
router.include_router(users_router)
router.include_router(documents_router)
router.include_router(folders_router)
