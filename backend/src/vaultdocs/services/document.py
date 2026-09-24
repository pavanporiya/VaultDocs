"""
Document service functions.
"""

from pathlib import Path
from uuid import UUID, uuid4

from fastapi import UploadFile
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from vaultdocs.core.settings import settings
from vaultdocs.models.document import Document
from vaultdocs.models.document_share import DocumentShare
from vaultdocs.models.document_version import DocumentVersion
from vaultdocs.models.folder import Folder
from vaultdocs.models.user import User
from vaultdocs.schemas.document import DocumentCreate, DocumentUpdate
from vaultdocs.services.folder import get_folder_by_id


async def get_document_by_id(
    db: AsyncSession,
    document_id: UUID,
) -> Document | None:
    """
    Retrieve a document by its UUID.
    """
    result = await db.execute(
        select(Document).where(Document.id == document_id),
    )
    return result.scalar_one_or_none()


async def get_user_document_by_id(
    db: AsyncSession,
    document_id: UUID,
    owner_id: UUID,
) -> Document | None:
    """
    Retrieve a document by ID only if it belongs to the specified owner.
    """
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.owner_id == owner_id,
        ),
    )
    return result.scalar_one_or_none()


async def list_user_documents(
    db: AsyncSession,
    owner_id: UUID,
) -> list[Document]:
    """
    List all documents belonging to a given user.
    """
    result = await db.execute(
        select(Document).where(Document.owner_id == owner_id).order_by(Document.created_at.asc()),
    )
    return list(result.scalars().all())


async def search_user_documents(
    db: AsyncSession,
    owner_id: UUID,
    q: str | None = None,
    folder_id: UUID | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> list[Document]:
    """
    Search documents owned by a specific user with optional name search, folder filter,
    and pagination.
    """
    query = select(Document).where(Document.owner_id == owner_id)

    if q is not None and q.strip():
        search_pattern = f"%{q.strip()}%"
        query = query.where(Document.name.ilike(search_pattern))

    if folder_id is not None:
        query = query.where(Document.folder_id == folder_id)

    query = query.order_by(Document.created_at.desc())

    if offset is not None and offset > 0:
        query = query.offset(offset)

    if limit is not None and limit > 0:
        query = query.limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())


async def validate_document_folder(
    db: AsyncSession,
    owner_id: UUID,
    folder_id: UUID,
) -> Folder:
    """
    Validate that target folder exists and belongs to the specified owner.
    """
    folder = await get_folder_by_id(db, folder_id)
    if folder is None:
        raise ValueError("Folder not found.")

    if folder.owner_id != owner_id:
        raise ValueError("Folder does not belong to user.")

    return folder


async def create_document(
    db: AsyncSession,
    owner_id: UUID,
    document_data: DocumentCreate,
) -> Document:
    """
    Create a new document for a user.
    """
    name = document_data.name.strip()
    if not name:
        raise ValueError("Document name cannot be empty.")

    if document_data.folder_id is not None:
        await validate_document_folder(
            db=db,
            owner_id=owner_id,
            folder_id=document_data.folder_id,
        )

    document = Document(
        name=name,
        owner_id=owner_id,
        folder_id=document_data.folder_id,
    )

    db.add(document)
    await db.commit()
    await db.refresh(document)
    return document


async def update_document(
    db: AsyncSession,
    document: Document,
    update_data: DocumentUpdate,
) -> Document:
    """
    Update an existing document.
    """
    fields_set = update_data.model_dump(exclude_unset=True)

    if "name" in fields_set:
        if update_data.name is None or not update_data.name.strip():
            raise ValueError("Document name cannot be empty.")
        document.name = update_data.name.strip()

    if "folder_id" in fields_set:
        new_folder_id = update_data.folder_id
        if new_folder_id is not None:
            await validate_document_folder(
                db=db,
                owner_id=document.owner_id,
                folder_id=new_folder_id,
            )
        document.folder_id = new_folder_id

    await db.commit()
    await db.refresh(document)
    return document


async def delete_document(
    db: AsyncSession,
    document: Document,
) -> None:
    """
    Delete a document.
    """
    await db.delete(document)
    await db.commit()


async def upload_document_file(
    db: AsyncSession,
    document: Document,
    file: UploadFile,
) -> Document:
    """
    Safely stream and store an uploaded file for an existing document.
    Handles initial upload, replacement, and preserves version history.
    """
    raw_filename = file.filename or "unnamed_file"
    safe_original_filename = Path(raw_filename).name
    if not safe_original_filename or safe_original_filename in (".", ".."):
        safe_original_filename = "unnamed_file"

    storage_dir = Path(settings.storage_dir).resolve()
    storage_dir.mkdir(parents=True, exist_ok=True)

    extension = Path(safe_original_filename).suffix
    unique_storage_filename = f"{uuid4().hex}{extension}"
    dest_file_path = (storage_dir / unique_storage_filename).resolve()

    try:
        is_inside = dest_file_path.is_relative_to(storage_dir)
    except ValueError:
        is_inside = False

    if not is_inside:
        raise ValueError("Invalid file path: path outside storage directory.")

    # Determine next version number and handle legacy unversioned files
    max_ver_result = await db.execute(
        select(func.max(DocumentVersion.version_number)).where(
            DocumentVersion.document_id == document.id
        )
    )
    current_max_version = max_ver_result.scalar_one_or_none()

    if current_max_version is None:
        if document.file_path is not None:
            legacy_version = DocumentVersion(
                document_id=document.id,
                version_number=1,
                file_path=document.file_path,
                original_filename=document.original_filename or "unnamed_file",
                file_size=document.file_size or 0,
                content_type=document.content_type or "application/octet-stream",
            )
            db.add(legacy_version)
            next_version_number = 2
        else:
            next_version_number = 1
    else:
        next_version_number = current_max_version + 1

    chunk_size = 64 * 1024  # 64KB
    total_size = 0

    try:
        with dest_file_path.open("wb") as buffer:
            while chunk := await file.read(chunk_size):
                total_size += len(chunk)
                if total_size > settings.max_upload_size:
                    raise ValueError(
                        f"File size exceeds maximum allowed limit of "
                        f"{settings.max_upload_size} bytes."
                    )
                buffer.write(chunk)
    except Exception:
        if dest_file_path.exists():
            dest_file_path.unlink()
        raise

    document.file_path = str(dest_file_path)
    document.original_filename = safe_original_filename
    document.file_size = total_size
    document.content_type = file.content_type or "application/octet-stream"

    new_version = DocumentVersion(
        document_id=document.id,
        version_number=next_version_number,
        file_path=str(dest_file_path),
        original_filename=safe_original_filename,
        file_size=total_size,
        content_type=document.content_type,
    )
    db.add(new_version)

    try:
        await db.commit()
        await db.refresh(document)
    except Exception:
        await db.rollback()
        if dest_file_path.exists():
            dest_file_path.unlink()
        raise

    return document


async def list_documents_shared_with_user(
    db: AsyncSession,
    user_id: UUID,
) -> list[tuple[Document, User, DocumentShare]]:
    """
    List all documents shared with a specific user (read-only recipients).

    Returns (document, owner, share) tuples ordered by share creation,
    newest first.
    """
    result = await db.execute(
        select(Document, User, DocumentShare)
        .join(DocumentShare, DocumentShare.document_id == Document.id)
        .join(User, Document.owner_id == User.id)
        .where(DocumentShare.shared_with_user_id == user_id)
        .order_by(DocumentShare.created_at.desc())
    )
    return [(doc, owner, share) for doc, owner, share in result.all()]


def get_document_file_path(document: Document) -> Path:
    """
    Validate and return the resolved file path for a document.
    Ensures the path exists, is a file, and resides strictly inside storage_dir.
    Raises ValueError if missing, invalid, non-existent, or path traversal attempt.
    """
    if not document.file_path:
        raise ValueError("Document has no file uploaded.")

    storage_dir = Path(settings.storage_dir).resolve()
    target_path = Path(document.file_path).resolve()

    try:
        is_inside = target_path.is_relative_to(storage_dir)
    except ValueError:
        is_inside = False

    if not is_inside:
        raise ValueError("Invalid file path: path outside storage directory.")

    if not target_path.exists() or not target_path.is_file():
        raise ValueError("Document file does not exist on disk.")

    return target_path


async def list_document_versions(
    db: AsyncSession,
    document_id: UUID,
) -> list[DocumentVersion]:
    """
    List all versions for a document ordered by version_number descending.
    """
    result = await db.execute(
        select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version_number.desc())
    )
    return list(result.scalars().all())


async def get_document_version_by_id(
    db: AsyncSession,
    document_id: UUID,
    version_id: UUID,
) -> DocumentVersion | None:
    """
    Retrieve a specific document version by version ID and document ID.
    """
    result = await db.execute(
        select(DocumentVersion).where(
            DocumentVersion.id == version_id,
            DocumentVersion.document_id == document_id,
        )
    )
    return result.scalar_one_or_none()


def get_version_file_path(version: DocumentVersion) -> Path:
    """
    Validate and return the resolved file path for a document version.
    Ensures the path exists, is a file, and resides strictly inside storage_dir.
    Raises ValueError if missing, invalid, non-existent, or path traversal attempt.
    """
    if not version.file_path:
        raise ValueError("Version has no file uploaded.")

    storage_dir = Path(settings.storage_dir).resolve()
    target_path = Path(version.file_path).resolve()

    try:
        is_inside = target_path.is_relative_to(storage_dir)
    except ValueError:
        is_inside = False

    if not is_inside:
        raise ValueError("Invalid file path: path outside storage directory.")

    if not target_path.exists() or not target_path.is_file():
        raise ValueError("Version file does not exist on disk.")

    return target_path
