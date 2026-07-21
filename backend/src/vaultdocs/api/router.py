"""
Main API router.
"""

from fastapi import APIRouter

from vaultdocs.api.v1.router import router as v1_router

router = APIRouter()

router.include_router(v1_router)
