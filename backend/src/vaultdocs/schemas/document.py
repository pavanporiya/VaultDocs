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
    extraction_status: str | None = Field(
        default=None,
        description="Document intelligence status (pending/processing/completed/...).",
    )
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


class DocumentIntelligenceResponse(BaseModel):
    """
    Response schema for document intelligence (extraction, tags, summary).

    Readable by anyone with read access to the document (owner and share
    recipients): it exposes derived text metadata only — never raw file bytes
    or download paths. Includes the same computed permission flags as
    ``DocumentResponse`` so the UI can gate the re-index action.
    """

    document_id: UUID = Field(
        description="ID of the document this intelligence belongs to.",
    )

    status: str | None = Field(
        default=None,
        description=(
            "Extraction status: pending | processing | completed | unsupported | "
            "encrypted | no_text | failed. None means no file was ever uploaded."
        ),
    )

    file_ready: bool = Field(
        default=False,
        description="True when a file is stored for this document.",
    )

    page_count: int | None = Field(
        default=None,
        description="Page count when available (PDF).",
    )

    char_count: int | None = Field(
        default=None,
        description="Number of extracted characters persisted.",
    )

    tags: list[str] = Field(
        default_factory=list,
        description="Generated tags (format tag + content keywords).",
    )

    summary: str | None = Field(
        default=None,
        description="Generated summary. None when extraction produced no text.",
    )

    summary_source: str | None = Field(
        default=None,
        description="Provider that produced the summary (traceability).",
    )

    key_points: list[str] = Field(
        default_factory=list,
        description="Verbatim high-salience sentences quoted from the source text.",
    )

    error: str | None = Field(
        default=None,
        description="Human-readable extraction failure reason, if any.",
    )

    extracted_at: datetime | None = Field(
        default=None,
        description="When extraction last completed.",
    )

    # Computed authorization metadata for the requesting user (same contract
    # as DocumentResponse: owner defaults, overridden for share recipients).
    is_owner: bool = Field(default=True, description="True if the requester owns this document.")
    permission: DocumentPermission = Field(
        default="owner",
        description='Effective permission: "owner" | "viewer".',
    )
    can_edit: bool = Field(default=True, description="True if the user may modify the document.")
    can_download: bool = Field(default=True, description="False for view-only recipients.")
    can_share: bool = Field(default=True, description="True only for the document owner.")
    can_delete: bool = Field(default=True, description="True only for the document owner.")


class DocumentSearchHit(DocumentResponse):
    """
    A content-search hit: document metadata plus relevance details.

    Only documents the requester can read (owned or actively shared) are ever
    returned; permission filtering happens before scoring.
    """

    score: float = Field(
        default=0.0,
        description="Relevance score (higher is a better match).",
    )

    snippet: str = Field(
        default="",
        description="Short excerpt around the best-matching chunk.",
    )

    matched_chunk: int | None = Field(
        default=None,
        description="Index of the best-matching chunk within the document.",
    )
