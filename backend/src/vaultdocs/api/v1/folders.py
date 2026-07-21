"""
Folder API endpoints.
"""

from fastapi import APIRouter

router = APIRouter(
    prefix="/folders",
    tags=["Folders"],
)
