"""
Pydantic schemas.
"""

from vaultdocs.schemas.document import (
    DocumentCreate,
    DocumentResponse,
    DocumentUpdate,
    DocumentVersionResponse,
    SharedDocumentResponse,
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
from vaultdocs.schemas.user import (
    UserPreferencesResponse,
    UserUpdate,
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
    "SharedDocumentResponse",
    "UserPreferencesResponse",
    "UserUpdate",
]
