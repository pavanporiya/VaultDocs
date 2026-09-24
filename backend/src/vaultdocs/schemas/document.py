"""
Document request and response schemas.
"""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

DocumentPermission = Literal["owner", "viewer"]


class DocumentCreate(BaseModel):
    """
    Request body for creating a document.
    """

    name: str = Field(
        min_length=1,
        max_length=255,
        description="Name of the document.",
    )

    folder_id: UUID | None = Field(
        default=None,
        description="ID of the folder containing the document.",
    )


class DocumentUpdate(BaseModel):
    """
    Request body for updating a document.
    """

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
        description="Updated name of the document.",
    )

    folder_id: UUID | None = Field(
        default=None,
        description="Updated folder ID containing the document.",
    )


class DocumentResponse(BaseModel):
    """
    Response schema for document operations.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    owner_id: UUID
    folder_id: UUID | None
    file_path: str | None = None
    original_filename: str | None = None
    file_size: int | None = None
    content_type: str | None = None
    created_at: datetime
    updated_at: datetime

    # ------------------------------------------------------------------
    # Computed authorization metadata for the requesting user.
    # Defaults describe the OWNER (listing endpoints are owner-scoped, so
    # every row returned there is the requester's own document). Recipient
    # endpoints construct responses with viewer flags explicitly.
    # ------------------------------------------------------------------
    is_owner: bool = Field(
        default=True,
        description="True if the requesting user owns this document.",
    )
    permission: DocumentPermission = Field(
        default="owner",
        description='Effective permission of the requesting user: "owner" | "viewer".',
    )
    can_edit: bool = Field(
        default=True,
        description="True if the user may upload/replace files or rename/move the document.",
    )
    can_download: bool = Field(
        default=True,
        description="False when the user has view-only (seen) access without download rights.",
    )
    can_share: bool = Field(
        default=True,
        description="True only for the document owner.",
    )
    can_delete: bool = Field(
        default=True,
        description="True only for the document owner.",
    )


def owner_permission_flags() -> dict[str, bool | str]:
    """
    Flag set for the document owner (default field values, explicit for clarity).
    """
    return {
        "is_owner": True,
        "permission": "owner",
        "can_edit": True,
        "can_download": True,
        "can_share": True,
        "can_delete": True,
    }


def viewer_permission_flags(*, can_download: bool) -> dict[str, bool | str]:
    """
    Flag set for a read-only share recipient.

    VaultDocs shares are strictly "seen" (view/preview only): the recipient
    can read metadata and preview in-browser, but can never edit, share, or
    delete. Downloading is governed by the share's download grant.
    """
    return {
        "is_owner": False,
        "permission": "viewer",
        "can_edit": False,
        "can_download": can_download,
        "can_share": False,
        "can_delete": False,
    }


class SharedDocumentResponse(DocumentResponse):
    """
    Response schema for documents shared with the current user.

    Extends DocumentResponse with read-only sharing context.
    """

    shared_by_name: str | None = Field(
        default=None,
        description="Full name of the document owner who shared it.",
    )

    shared_by_email: str | None = Field(
        default=None,
        description="Email of the document owner who shared it.",
    )

    shared_at: datetime | None = Field(
        default=None,
        description="Timestamp at which the share was created.",
    )

    is_owner: bool = Field(
        default=False,
        description="Recipients are never the owner.",
    )
    permission: DocumentPermission = Field(
        default="viewer",
        description='Recipients always have read-only ("seen") permission.',
    )
    can_edit: bool = Field(
        default=False,
        description="Recipients can never edit shared documents.",
    )
    can_download: bool = Field(
        default=True,
        description="True unless the share is strictly view-only (seen) without download.",
    )
    can_share: bool = Field(
        default=False,
        description="Recipients can never re-share.",
    )
    can_delete: bool = Field(
        default=False,
        description="Recipients can never delete shared documents.",
    )


class DocumentVersionResponse(BaseModel):
    """
    Response schema for document version operations.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    document_id: UUID
    version_number: int
    file_path: str
    original_filename: str
    file_size: int
    content_type: str
    created_at: datetime
