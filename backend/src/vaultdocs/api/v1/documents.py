"""
Document API endpoints.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from vaultdocs.api.dependencies.auth import get_current_user
from vaultdocs.db.session import get_db
from vaultdocs.models.user import User
from vaultdocs.schemas.document import (
    DocumentCreate,
    DocumentResponse,
    DocumentUpdate,
    DocumentVersionResponse,
)
from vaultdocs.services.document import (
    create_document,
    delete_document,
    get_document_by_id,
    get_document_file_path,
    get_document_version_by_id,
    get_version_file_path,
    list_document_versions,
    list_user_documents,
    search_user_documents,
    update_document,
    upload_document_file,
)

router = APIRouter(
    prefix="/documents",
    tags=["Documents"],
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
    Retrieve a specific document owned by the authenticated user.
    """
    document = await get_document_by_id(
        db=db,
        document_id=document_id,
    )
    if document is None or document.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    return DocumentResponse.model_validate(document)


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
    """
    document = await get_document_by_id(
        db=db,
        document_id=document_id,
    )
    if document is None or document.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

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
    """
    document = await get_document_by_id(
        db=db,
        document_id=document_id,
    )
    if document is None or document.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

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
    """
    document = await get_document_by_id(
        db=db,
        document_id=document_id,
    )
    if document is None or document.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

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
    Download the stored file for a document owned by the authenticated user.
    """
    document = await get_document_by_id(
        db=db,
        document_id=document_id,
    )
    if document is None or document.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
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
    "/{document_id}/versions",
    response_model=list[DocumentVersionResponse],
)
async def list_versions(
    document_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DocumentVersionResponse]:
    """
    List all versions for a document owned by the authenticated user, ordered newest first.
    """
    document = await get_document_by_id(
        db=db,
        document_id=document_id,
    )
    if document is None or document.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )

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
    if document is None or document.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
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
    """
    document = await get_document_by_id(
        db=db,
        document_id=document_id,
    )
    if document is None or document.owner_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
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
