"""
Pydantic schemas.
"""

from vaultdocs.schemas.document import (
    DocumentCreate,
    DocumentResponse,
    DocumentUpdate,
    DocumentVersionResponse,
)
from vaultdocs.schemas.folder import (
    FolderCreate,
    FolderResponse,
    FolderUpdate,
)
from vaultdocs.schemas.share import (
    ShareCreate,
    ShareResponse,
)

__all__ = [
    "DocumentCreate",
    "DocumentResponse",
    "DocumentUpdate",
    "DocumentVersionResponse",
    "FolderCreate",
    "FolderResponse",
    "FolderUpdate",
    "ShareCreate",
    "ShareResponse",
]
