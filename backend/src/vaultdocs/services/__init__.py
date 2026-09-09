"""
Service functions.
"""

from vaultdocs.services.document import (
    create_document,
    delete_document,
    get_document_by_id,
    list_user_documents,
    update_document,
    validate_document_folder,
)
from vaultdocs.services.folder import (
    create_folder,
    delete_folder,
    get_folder_by_id,
    list_user_folders,
    update_folder,
)

__all__ = [
    "create_document",
    "create_folder",
    "delete_document",
    "delete_folder",
    "get_document_by_id",
    "get_folder_by_id",
    "list_user_documents",
    "list_user_folders",
    "update_document",
    "update_folder",
    "validate_document_folder",
]
