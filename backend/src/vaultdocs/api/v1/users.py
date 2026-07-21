"""
User API endpoints.
"""

from fastapi import APIRouter

router = APIRouter(
    prefix="/users",
    tags=["Users"],
)
