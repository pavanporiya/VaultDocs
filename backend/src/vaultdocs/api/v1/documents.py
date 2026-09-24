"""
Document API endpoints.
"""

from pathlib import Path
from typing import TYPE_CHECKING
from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from vaultdocs.api.dependencies.auth import get_current_user
from vaultdocs.db.session import get_db
from vaultdocs.models.user import User

if TYPE_CHECKING:
    from vaultdocs.models.document import Document
from vaultdocs.schemas.document import (
    DocumentCreate,
    DocumentResponse,
    DocumentUpdate,
    DocumentVersionResponse,
    SharedDocumentResponse,
    owner_permission_flags,
    viewer_permission_flags,
)
from vaultdocs.services.document import (
    create_document,
    delete_document,
    get_document_by_id,
    get_document_file_path,
    get_document_version_by_id,
    get_version_file_path,
    list_document_versions,
    list_documents_shared_with_user,
    list_user_documents,
    search_user_documents,
    update_document,
    upload_document_file,
)
from vaultdocs.services.share import (
    get_user_download_permission,
    user_can_access_document,
    user_can_download_document,
)

router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
)

VIEW_ONLY_DOWNLOAD_MESSAGE = "Download disabled: you have view-only access to this document."

# Safe in-browser preview formats: rendered inline by browsers without
# plugins/scripts. Everything else is explicitly rejected.
PREVIEWABLE_INLINE_TYPES = {
    "application/pdf",
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
    "image/svg+xml",
    "image/bmp",
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/json",
}

# Text/media bytes allowed through the preview stream (mirrors upload cap).
MAX_PREVIEW_INLINE_BYTES = 10 * 1024 * 1024

# Extension fallbacks when content_type is missing/generic (mirrors the
# frontend's fileTypes.js classification).
_PREVIEW_EXTENSION_TYPES = {
    "pdf": "application/pdf",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "gif": "image/gif",
    "webp": "image/webp",
    "svg": "image/svg+xml",
    "bmp": "image/bmp",
    "txt": "text/plain",
    "md": "text/markdown",
    "csv": "text/csv",
    "json": "application/json",
}


def _resolve_preview_type(
    content_type: str | None,
    original_filename: str | None,
) -> str | None:
    """
    Resolve the safe inline preview media type, or None if unsupported.
    """
    type_ = (content_type or "").lower().split(";")[0].strip()
    if type_ in PREVIEWABLE_INLINE_TYPES:
        return type_

    extension = (original_filename or "").rsplit(".", 1)[-1].lower()
    return _PREVIEW_EXTENSION_TYPES.get(extension)


def _validate_preview_file(
    file_path: Path,
    original_filename: str | None,
    content_type: str | None,
) -> tuple[Path, str, str]:
    """
    Validate a document file for inline preview streaming.

    Returns (path, media_type, inline_filename).
    Raises ValueError when the type is unsupported or the file is too large.
    """
    media_type = _resolve_preview_type(content_type, original_filename)
    if media_type is None:
        raise ValueError("Preview is not available for this file type.")

    if file_path.stat().st_size > MAX_PREVIEW_INLINE_BYTES:
        raise ValueError("File is too large to preview.")

    return file_path, media_type, original_filename or "preview"


async def _get_document_for_request(
    db: AsyncSession,
    document_id: UUID,
    current_user: User,
) -> tuple["Document | None", dict[str, bool | str]]:
    """
    Fetch a document and compute the requester's authorization flags.

    Returns (None, {}) when the document does not exist or the user has no
    access to it. Owners get full flags; share recipients get view-only
    flags (shares are strictly "seen": no edit/share/delete for viewers).
    """
    document = await get_document_by_id(db=db, document_id=document_id)
    if document is None:
        return None, {}

    if document.owner_id == current_user.id:
        return document, owner_permission_flags()

    if not await user_can_access_document(db=db, document=document, user=current_user):
        return None, {}

    can_download = await get_user_download_permission(
        db=db,
        document=document,
        user=current_user,
    )
    return document, viewer_permission_flags(can_download=can_download)


def _raise_not_found() -> HTTPException:
    """
    Safe 404 for documents the user cannot see (never disclose existence).
    """
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Document not found.",
    )


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_new_document(
    document_data: DocumentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """
    Create a new document for the authenticated user.
    """
    try:
        document = await create_document(
            db=db,
            owner_id=current_user.id,
            document_data=document_data,
        )
        return DocumentResponse.model_validate(document)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "",
    response_model=list[DocumentResponse],
)
async def list_documents(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentResponse]:
    """
    List all documents owned by the authenticated user.
    """
    documents = await list_user_documents(
        db=db,
        owner_id=current_user.id,
    )
    return [DocumentResponse.model_validate(d) for d in documents]


@router.get(
    "/shared",
    response_model=list[SharedDocumentResponse],
)
async def list_shared_with_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[SharedDocumentResponse]:
    """
    List all documents shared with the authenticated user (read-only).
    """
    rows = await list_documents_shared_with_user(
        db=db,
        user_id=current_user.id,
    )

    return [
        SharedDocumentResponse(
            id=doc.id,
            name=doc.name,
            owner_id=doc.owner_id,
            folder_id=doc.folder_id,
            # file_path is intentionally NOT exposed to recipients.
            file_path=None,
            original_filename=doc.original_filename,
            file_size=doc.file_size,
            content_type=doc.content_type,
            created_at=doc.created_at,
            updated_at=doc.updated_at,
            shared_by_name=owner.full_name,
            shared_by_email=owner.email,
            shared_at=share.created_at,
            is_owner=False,
            permission="viewer",
            can_edit=False,
            can_download=share.download_allowed,
            can_share=False,
            can_delete=False,
        )
        for doc, owner, share in rows
    ]


@router.get(
    "/search",
    response_model=list[DocumentResponse],
)
async def search_documents(
    q: str | None = Query(default=None),
    folder_id: UUID | None = Query(default=None),
    limit: int | None = Query(default=None, ge=1, le=100),
    offset: int | None = Query(default=None, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentResponse]:
    """
    Search documents owned by the authenticated user with optional name query, folder filter,
    and pagination.
    """
    documents = await search_user_documents(
        db=db,
        owner_id=current_user.id,
        q=q,
        folder_id=folder_id,
        limit=limit,
        offset=offset,
    )
    return [DocumentResponse.model_validate(d) for d in documents]


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
)
async def get_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """
    Retrieve a specific document owned by the authenticated user, or shared
    with them in view-only ("seen") mode.

    The response includes computed authorization flags (is_owner, permission,
    can_edit, can_download, can_share, can_delete) for the requesting user.
    """
    document, flags = await _get_document_for_request(
        db=db,
        document_id=document_id,
        current_user=current_user,
    )
    if document is None:
        raise _raise_not_found()

    response = DocumentResponse.model_validate(document)
    for field, value in flags.items():
        setattr(response, field, value)
    return response


@router.patch(
    "/{document_id}",
    response_model=DocumentResponse,
)
async def update_existing_document(
    document_id: UUID,
    update_data: DocumentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """
    Update a document owned by the authenticated user.

    Non-owners are rejected: outsiders with a safe 404 (existence not
    disclosed), share recipients with a clean 403 Forbidden.
    """
    document = await get_document_by_id(
        db=db,
        document_id=document_id,
    )
    if document is None:
        raise _raise_not_found()

    if document.owner_id != current_user.id:
        if await user_can_access_document(db=db, document=document, user=current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You have read-only access to this document.",
            )
        raise _raise_not_found()

    try:
        updated_document = await update_document(
            db=db,
            document=document,
            update_data=update_data,
        )
        return DocumentResponse.model_validate(updated_document)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_existing_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """
    Delete a document owned by the authenticated user.

    Non-owners are rejected: outsiders with a safe 404, share recipients
    with a clean 403 Forbidden.
    """
    document = await get_document_by_id(
        db=db,
        document_id=document_id,
    )
    if document is None:
        raise _raise_not_found()

    if document.owner_id != current_user.id:
        if await user_can_access_document(db=db, document=document, user=current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You have read-only access to this document.",
            )
        raise _raise_not_found()

    await delete_document(
        db=db,
        document=document,
    )


@router.post(
    "/{document_id}/upload",
    response_model=DocumentResponse,
)
@router.put(
    "/{document_id}/upload",
    response_model=DocumentResponse,
)
async def upload_document(
    document_id: UUID,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """
    Upload or replace a file for an existing document owned by the authenticated user.

    Non-owners are rejected: outsiders with a safe 404, share recipients
    with a clean 403 Forbidden.
    """
    document = await get_document_by_id(
        db=db,
        document_id=document_id,
    )
    if document is None:
        raise _raise_not_found()

    if document.owner_id != current_user.id:
        if await user_can_access_document(db=db, document=document, user=current_user):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You have read-only access to this document.",
            )
        raise _raise_not_found()

    try:
        updated_document = await upload_document_file(
            db=db,
            document=document,
            file=file,
        )
        return DocumentResponse.model_validate(updated_document)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get(
    "/{document_id}/download",
    response_class=FileResponse,
)
async def download_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """
    Download the stored file for a document owned by the authenticated user,
    or shared with them.

    Share recipients may download only when their share grants it; a strictly
    view-only ("seen") share allows safe in-browser preview but blocks raw
    file downloads with 403 Forbidden.
    """
    document = await get_document_by_id(
        db=db,
        document_id=document_id,
    )
    if document is None or not await user_can_access_document(
        db=db,
        document=document,
        user=current_user,
    ):
        raise _raise_not_found()

    if not await user_can_download_document(db=db, document=document, user=current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=VIEW_ONLY_DOWNLOAD_MESSAGE,
        )

    try:
        file_path = get_document_file_path(document)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found.",
        ) from exc

    filename = document.original_filename or "download"
    media_type = document.content_type or "application/octet-stream"

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=media_type,
    )


@router.get(
    "/{document_id}/preview",
    response_class=Response,
)
async def preview_document(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    """
    Stream a previewable document file inline for safe in-browser preview.

    Accessible to the owner and share recipients (including strictly view-only
    / "seen" shares) — preview is the read path that replaces raw downloads
    for restricted users. No Content-Disposition: attachment header is ever
    emitted, so this endpoint can never trigger a browser save dialog.

    Unsupported formats are rejected with a distinct 400 so the UI can show
    "preview unavailable" without offering an unauthorized download path.
    """
    document = await get_document_by_id(
        db=db,
        document_id=document_id,
    )
    if document is None or not await user_can_access_document(
        db=db,
        document=document,
        user=current_user,
    ):
        raise _raise_not_found()

    try:
        file_path = get_document_file_path(document)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document file not found.",
        ) from exc

    try:
        file_path, media_type, inline_name = _validate_preview_file(
            file_path,
            document.original_filename,
            document.content_type,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    # StreamingResponse via Response: media bytes only, rendered inline.
    # No attachment header, no filename-for-download, no version targeting.
    return Response(
        content=file_path.read_bytes(),
        media_type=media_type,
        headers={
            "Content-Disposition": f'inline; filename="{inline_name}"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )


@router.get(
    "/{document_id}/versions",
    response_model=list[DocumentVersionResponse],
)
async def list_versions(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentVersionResponse]:
    """
    List all versions for a document owned by the authenticated user, or shared
    with them in view-only ("seen") mode, ordered newest first.
    """
    document = await get_document_by_id(
        db=db,
        document_id=document_id,
    )
    if document is None or not await user_can_access_document(
        db=db,
        document=document,
        user=current_user,
    ):
        raise _raise_not_found()

    versions = await list_document_versions(
        db=db,
        document_id=document_id,
    )
    return [DocumentVersionResponse.model_validate(v) for v in versions]


@router.get(
    "/{document_id}/versions/{version_id}",
    response_model=DocumentVersionResponse,
)
async def get_version(
    document_id: UUID,
    version_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentVersionResponse:
    """
    Retrieve details of a specific document version.
    """
    document = await get_document_by_id(
        db=db,
        document_id=document_id,
    )
    if document is None or not await user_can_access_document(
        db=db,
        document=document,
        user=current_user,
    ):
        raise _raise_not_found()

    version = await get_document_version_by_id(
        db=db,
        document_id=document_id,
        version_id=version_id,
    )
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found.",
        )

    return DocumentVersionResponse.model_validate(version)


@router.get(
    "/{document_id}/versions/{version_id}/download",
    response_class=FileResponse,
)
async def download_version(
    document_id: UUID,
    version_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> FileResponse:
    """
    Download the file for a specific document version.

    Share recipients may download only when their share grants it; a strictly
    view-only ("seen") share blocks version downloads with 403 Forbidden.
    """
    document = await get_document_by_id(
        db=db,
        document_id=document_id,
    )
    if document is None or not await user_can_access_document(
        db=db,
        document=document,
        user=current_user,
    ):
        raise _raise_not_found()

    if not await user_can_download_document(db=db, document=document, user=current_user):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=VIEW_ONLY_DOWNLOAD_MESSAGE,
        )

    version = await get_document_version_by_id(
        db=db,
        document_id=document_id,
        version_id=version_id,
    )
    if version is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found.",
        )

    try:
        file_path = get_version_file_path(version)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version file not found.",
        ) from exc

    filename = version.original_filename or "download"
    media_type = version.content_type or "application/octet-stream"

    return FileResponse(
        path=file_path,
        filename=filename,
        media_type=media_type,
    )
