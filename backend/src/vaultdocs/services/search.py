"""
Content search over extracted document text.

Design notes:

- Permissions are enforced in the candidate query itself: only documents the
  user owns or that are actively shared with them are ever loaded, so a
  revoked share or another user's document can never appear in results —
  regardless of relevance.
- No separate index table exists, therefore no duplicate or stale index rows
  can exist either: results are always derived from the persisted
  ``documents.extracted_text`` at query time. Deletions, replacements, and
  share revocations take effect immediately with no re-index bookkeeping.
- Pure-Python lexical scoring (chunked) is used because no embedding library
  or vector store is available/approved in this environment. When no content
  matches are found, callers fall back to the pre-existing name-based search.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sqlalchemy import and_, or_, select

if TYPE_CHECKING:
    from uuid import UUID

    from sqlalchemy.ext.asyncio import AsyncSession

from vaultdocs.core.settings import settings
from vaultdocs.models.document import Document
from vaultdocs.models.document_share import DocumentShare

#: Extra characters of context captured on each side of a snippet anchor.
SNIPPET_RADIUS = 120

_QUERY_TOKEN_RE = re.compile(r"[\w'-]{2,}", re.UNICODE)


@dataclass(frozen=True, slots=True)
class ContentSearchMatch:
    """A single scored document hit returned by content search."""

    document: Document
    score: float
    snippet: str
    chunk_index: int


def tokenize_query(query: str) -> list[str]:
    """Lowercased query terms of length >= 2; empty list for blank queries."""
    return [token.lower() for token in _QUERY_TOKEN_RE.findall(query) if len(token) >= 2]


def chunk_text(text: str, *, size: int, overlap: int) -> list[str]:
    """
    Split ``text`` into overlapping chunks of about ``size`` characters,
    preferring word boundaries. Guarantees forward progress and no gaps
    between consecutive chunks.
    """
    clean = text.strip()
    if not clean:
        return []
    if size < 1:
        raise ValueError("Chunk size must be >= 1.")

    step = max(size - max(overlap, 0), max(size // 4, 1))
    total = len(clean)
    chunks: list[str] = []
    position = 0

    while position < total:
        end = min(position + size, total)
        if end < total:
            boundary = clean.rfind(" ", position + size // 2, end)
            if boundary > position:
                end = boundary

        chunk = clean[position:end].strip()
        if chunk:
            chunks.append(chunk)

        if position + size >= total:
            break

        # Never skip past the word boundary actually used (no coverage gaps).
        position = min(position + step, end)

    return chunks


def score_chunk(terms: list[str], query: str, chunk: str) -> float:
    """Lexical relevance of a chunk: term coverage x frequency, phrase bonus."""
    if not terms:
        return 0.0

    lowered = chunk.lower()
    score = 0.0
    matched_terms = 0

    for term in terms:
        occurrences = lowered.count(term)
        if occurrences:
            matched_terms += 1
            score += 1.0 + math.log1p(occurrences)

    if matched_terms == 0:
        return 0.0

    # Coverage weight: matching more of the query beats matching one term hard.
    score *= matched_terms / len(terms)

    normalized_query = " ".join(query.split()).lower()
    if normalized_query and normalized_query in lowered:
        score += 3.0

    return score


def build_snippet(chunk: str, terms: list[str]) -> str:
    """Short excerpt centred on the earliest query-term match."""
    lowered = chunk.lower()
    anchor = -1
    for term in terms:
        index = lowered.find(term)
        if index != -1 and (anchor == -1 or index < anchor):
            anchor = index

    if anchor == -1:
        return chunk[: SNIPPET_RADIUS * 2]

    start = max(anchor - SNIPPET_RADIUS, 0)
    end = min(anchor + SNIPPET_RADIUS, len(chunk))
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(chunk) else ""
    return f"{prefix}{chunk[start:end].strip()}{suffix}"


async def search_documents_by_content(
    db: AsyncSession,
    *,
    user_id: UUID,
    query: str,
    limit: int | None = None,
    offset: int | None = None,
) -> list[ContentSearchMatch]:
    """
    Permission-filtered, chunk-scored content search.

    Candidates are restricted to documents owned by ``user_id`` or actively
    shared with them (owner-scoped rows always allowed, share rows require an
    active DocumentShare). Returns the best matching chunk per document,
    ranked by score. Blank queries return no matches.
    """
    terms = tokenize_query(query)
    if not terms:
        return []

    stmt = (
        select(Document)
        .outerjoin(
            DocumentShare,
            and_(
                DocumentShare.document_id == Document.id,
                DocumentShare.shared_with_user_id == user_id,
            ),
        )
        .where(
            or_(
                Document.owner_id == user_id,
                DocumentShare.id.is_not(None),
            ),
            Document.extracted_text.is_not(None),
            Document.extracted_text != "",
        )
        .order_by(Document.updated_at.desc())
    )
    result = await db.execute(stmt)

    seen: set[UUID] = set()
    matches: list[ContentSearchMatch] = []

    for document in result.scalars().all():
        text = document.extracted_text
        if document.id in seen or not text:
            continue
        seen.add(document.id)

        chunks = chunk_text(
            text,
            size=settings.intelligence_chunk_chars,
            overlap=settings.intelligence_chunk_overlap,
        )

        best_index = -1
        best_score = 0.0
        for index, chunk in enumerate(chunks):
            score = score_chunk(terms, query, chunk)
            if score > best_score:
                best_score = score
                best_index = index

        if best_index < 0 or best_score <= 0.0:
            continue

        matches.append(
            ContentSearchMatch(
                document=document,
                score=round(best_score, 4),
                snippet=build_snippet(chunks[best_index], terms),
                chunk_index=best_index,
            )
        )

    matches.sort(key=lambda match: match.score, reverse=True)

    start = offset if offset and offset > 0 else 0
    stop = start + limit if limit and limit > 0 else len(matches)
    return matches[start:stop]
