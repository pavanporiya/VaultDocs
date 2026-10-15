"""
Document intelligence: metadata, auto-tagging, summaries, and the background
extraction job.

Rules honoured here (see the project brief):

- Source traceability: summaries record which provider produced them and are
  never mixed into "extracted facts" (tags/text/page count are extracted;
  summaries are generated).
- Provider abstraction: ``settings.ai_provider`` selects a provider; the
  default ``extractive`` provider is local, credential-free, and offline.
  If a remote provider is configured but unusable (missing key, network
  error, malformed response), the job falls back to the local provider —
  core VaultDocs keeps working with no AI credentials at all.
- No hardcoded API keys; secrets are never written to logs (provider errors
  are scrubbed and truncated before logging).
- Uploaded content is only read as bytes; it is never executed.
"""

import asyncio
import hashlib
import re
from collections import Counter
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vaultdocs.core.logging_config import get_logger
from vaultdocs.core.settings import settings
from vaultdocs.db.session import AsyncSessionLocal
from vaultdocs.models.document import Document
from vaultdocs.services.document import get_document_file_path
from vaultdocs.services.extraction import (
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PROCESSING,
    extract_text_from_file,
)

logger = get_logger(__name__)

# ------------------------------------------------------------------------------
# Tunables (module constants — no new settings keys needed)
# ------------------------------------------------------------------------------

#: Maximum tags returned (including the format tag).
MAX_TAGS = 10

#: Characters of text sampled for keyword extraction (performance guard).
TAGGING_SAMPLE_CHARS = 50_000

#: Characters of text fed to the local extractive summarizer.
EXTRACTIVE_INPUT_CHARS = 20_000

#: Hard cap on a stored summary.
SUMMARY_MAX_CHARS = 1_000

#: Cap for stored extraction error messages (column is String(512)).
MAX_ERROR_CHARS = 500

#: Format tag prefix so generated tags are distinguishable from keywords.
FORMAT_TAG_PREFIX = "type:"

_FORMAT_TAGS = {
    "pdf": "pdf",
    "docx": "document",
    "txt": "text",
    "md": "text",
    "markdown": "text",
    "csv": "tabular",
    "tsv": "tabular",
    "json": "data",
    "yaml": "data",
    "yml": "data",
    "log": "log",
}

_STOPWORDS = frozenset(
    [
        "about",
        "above",
        "after",
        "again",
        "against",
        "all",
        "also",
        "among",
        "and",
        "any",
        "are",
        "because",
        "been",
        "before",
        "being",
        "below",
        "between",
        "both",
        "but",
        "can",
        "cannot",
        "could",
        "did",
        "does",
        "doing",
        "down",
        "during",
        "each",
        "few",
        "for",
        "from",
        "further",
        "had",
        "has",
        "have",
        "having",
        "her",
        "here",
        "hers",
        "herself",
        "him",
        "himself",
        "his",
        "how",
        "into",
        "its",
        "itself",
        "just",
        "may",
        "more",
        "most",
        "much",
        "must",
        "not",
        "now",
        "off",
        "once",
        "only",
        "other",
        "our",
        "ours",
        "ourselves",
        "out",
        "over",
        "own",
        "same",
        "she",
        "should",
        "some",
        "such",
        "than",
        "that",
        "the",
        "their",
        "theirs",
        "them",
        "themselves",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "through",
        "under",
        "until",
        "very",
        "was",
        "were",
        "what",
        "when",
        "where",
        "which",
        "while",
        "who",
        "whom",
        "why",
        "will",
        "with",
        "would",
        "you",
        "your",
        "yours",
        "yourself",
    ]
)

_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_WORD_RE = re.compile(r"[A-Za-z][A-Za-z0-9'_-]{2,}")
_VALID_TAG_RE = re.compile(r"^[a-z0-9][a-z0-9:_-]{1,30}$")


# ------------------------------------------------------------------------------
# Fingerprinting (idempotency)
# ------------------------------------------------------------------------------


def compute_file_fingerprint(file_path: Path) -> str | None:
    """SHA-256 of the stored file bytes, or None when unreadable."""
    try:
        digest = hashlib.sha256()
        with file_path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def clip_error(message: str | None) -> str | None:
    """Trim an error message to fit documents.extraction_error (String(512))."""
    if message is None:
        return None
    cleaned = " ".join(message.split())
    return cleaned[:MAX_ERROR_CHARS]


# ------------------------------------------------------------------------------
# Auto-tagging
# ------------------------------------------------------------------------------


def generate_tags(
    *,
    text: str,
    filename: str | None = None,
    max_tags: int = MAX_TAGS,
) -> list[str]:
    """
    Generate validated, deduplicated tags from document content.

    Returns a format tag (``type:<kind>``) plus the most frequent
    non-stopword words. Output is validated against a strict pattern so
    malformed extraction output can never produce junk tags.
    """
    tags: list[str] = []

    extension = Path(filename).suffix.lower().lstrip(".") if filename else ""
    format_tag = _FORMAT_TAGS.get(extension)
    if format_tag:
        tags.append(f"{FORMAT_TAG_PREFIX}{format_tag}")

    sample = text[:TAGGING_SAMPLE_CHARS]
    tokens = [
        token.lower()
        for token in _WORD_RE.findall(sample)
        if token.lower() not in _STOPWORDS and not token.isdigit()
    ]

    for token, _count in Counter(tokens).most_common(max_tags * 3):
        candidate = token.strip("'_-")
        if len(candidate) < 3 or candidate in tags:
            continue
        if not _VALID_TAG_RE.fullmatch(candidate):
            continue
        tags.append(candidate)
        if len(tags) >= max_tags:
            break

    return tags


# ------------------------------------------------------------------------------
# Summaries (provider abstraction)
# ------------------------------------------------------------------------------


class SummaryProvider(Protocol):
    """Minimal async summary provider contract."""

    provider_name: str

    async def summarize(self, *, title: str, text: str) -> str:
        """Return a concise summary of ``text``. Raises on failure."""
        ...


def _split_sentences(text: str) -> list[str]:
    """Split text into trimmed, non-empty sentences."""
    sentences = [
        " ".join(part.split()) for part in _SENTENCE_SPLIT_RE.split(text) if part and part.strip()
    ]
    return [s for s in sentences if len(s) >= 3]


def _sentence_scores(sentences: Sequence[str]) -> list[float]:
    """Score sentences by stopword-filtered word frequency (length-adjusted)."""
    counts: Counter[str] = Counter()
    for sentence in sentences:
        for word in _WORD_RE.findall(sentence.lower()):
            if word not in _STOPWORDS and not word.isdigit():
                counts[word] += 1

    scores: list[float] = []
    for sentence in sentences:
        words = [w for w in _WORD_RE.findall(sentence.lower()) if w not in _STOPWORDS]
        if not words:
            scores.append(0.0)
            continue
        total = sum(counts[w] for w in words)
        scores.append(total / (len(words) ** 0.75))
    return scores


def build_extractive_summary(text: str, *, title: str = "") -> str:
    """Local, credential-free extractive summary: top sentences in order."""
    sample = text[:EXTRACTIVE_INPUT_CHARS]
    sentences = _split_sentences(sample)

    # Drop a heading line that merely repeats the document title.
    cleaned_title = " ".join(title.split()).lower().strip(" .")
    if (
        cleaned_title
        and sentences
        and " ".join(sentences[0].split()).lower().strip(" .") == cleaned_title
    ):
        sentences = sentences[1:]

    if not sentences:
        return ""

    scores = _sentence_scores(sentences)
    if not scores or max(scores) <= 0.0:
        return ""
    ranked = sorted(range(len(sentences)), key=lambda i: scores[i], reverse=True)

    chosen = sorted(ranked[:3])
    summary = " ".join(sentences[i] for i in chosen)
    return summary[:SUMMARY_MAX_CHARS]


def build_key_points(text: str, *, limit: int = 5) -> list[str]:
    """Top-scoring sentences from the source text, quoted verbatim."""
    sample = text[:EXTRACTIVE_INPUT_CHARS]
    sentences = _split_sentences(sample)
    if not sentences:
        return []

    scores = _sentence_scores(sentences)
    ranked = sorted(range(len(sentences)), key=lambda i: scores[i], reverse=True)
    return [sentences[i][:300] for i in ranked[:limit] if scores[i] > 0]


class ExtractiveSummaryProvider:
    """Offline extractive summarizer — the safe default (no credentials)."""

    provider_name = "extractive"

    async def summarize(self, *, title: str, text: str) -> str:
        """Return the highest-ranked sentences from the source text."""
        return build_extractive_summary(text, title=title)


class OpenAICompatibleSummaryProvider:
    """Remote chat-completions provider (OpenAI-compatible HTTP API)."""

    provider_name = "openai_compatible"

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        api_key: str | None,
        timeout: float,
        max_input_chars: int,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._timeout = timeout
        self._max_input_chars = max_input_chars

    async def summarize(self, *, title: str, text: str) -> str:
        """Call /chat/completions and return the assistant message content."""
        if not self._api_key:
            raise ValueError("AI provider is not configured (missing API key).")

        prompt = (
            "Summarize the following document in at most 3 concise sentences. "
            "Only use information present in the text; do not guess.\n\n"
            f"Title: {title}\n\nText:\n{text[: self._max_input_chars]}"
        )
        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": "You summarize documents faithfully."},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
            "max_tokens": 300,
        }
        headers = {"Authorization": f"Bearer {self._api_key}"}
        url = f"{self._base_url}/chat/completions"

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("AI provider returned an unexpected response shape.") from exc

        if not isinstance(content, str) or not content.strip():
            raise ValueError("AI provider returned an empty summary.")

        return content.strip()[:SUMMARY_MAX_CHARS]


def get_summary_provider() -> SummaryProvider:
    """
    Resolve the configured summary provider.

    Falls back to the local extractive provider whenever the configured
    provider is unknown or has no credentials — missing AI configuration can
    never break VaultDocs.
    """
    name = settings.ai_provider.strip().lower()

    if name in {"openai_compatible", "openai", "http"}:
        if settings.ai_api_key:
            return OpenAICompatibleSummaryProvider(
                base_url=settings.ai_base_url,
                model=settings.ai_model,
                api_key=settings.ai_api_key,
                timeout=settings.ai_timeout_seconds,
                max_input_chars=settings.ai_max_input_chars,
            )
        logger.warning(
            "AI provider '%s' requested but no API key is configured; "
            "falling back to local extractive summaries.",
            name,
        )
        return ExtractiveSummaryProvider()

    if name != "extractive":
        logger.warning("Unknown AI provider '%s'; using local extractive summaries.", name)

    return ExtractiveSummaryProvider()


def _scrub_secrets(message: str) -> str:
    """Remove the configured API key from a message before it reaches logs."""
    scrubbed = message
    if settings.ai_api_key and settings.ai_api_key in scrubbed:
        scrubbed = scrubbed.replace(settings.ai_api_key, "***")
    return scrubbed


async def generate_summary(text: str, *, title: str) -> tuple[str, str]:
    """
    Generate a summary, returning ``(summary, source)``.

    ``source`` names the provider that produced the summary so the API can
    preserve traceability. Failures fall back to the local provider instead
    of failing the extraction job.
    """
    if not text.strip():
        return "", "none"

    provider = get_summary_provider()
    try:
        summary = await provider.summarize(title=title, text=text)
    except Exception as exc:  # remote provider failures must never break the job
        logger.warning(
            "Summary provider '%s' failed (%s: %s); using extractive fallback.",
            provider.provider_name,
            type(exc).__name__,
            _scrub_secrets(str(exc))[:200],
        )
        return (
            build_extractive_summary(text, title=title),
            ExtractiveSummaryProvider.provider_name,
        )

    cleaned = " ".join(summary.split())
    if not cleaned:
        return (
            build_extractive_summary(text, title=title),
            ExtractiveSummaryProvider.provider_name,
        )

    return cleaned[:SUMMARY_MAX_CHARS], provider.provider_name


# ------------------------------------------------------------------------------
# Background extraction job
# ------------------------------------------------------------------------------


async def run_document_intelligence(
    document_id: UUID,
    *,
    force: bool = False,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """
    Extract text, tags, and a summary for one document and persist the result.

    Idempotent: re-running for an unchanged file (same SHA-256) is a no-op
    unless ``force`` is set. Safe to retry — a failure is recorded on the
    document row instead of raising out of the background task. Documents
    deleted before the job runs simply disappear (no orphan index rows).
    """
    factory = session_factory or AsyncSessionLocal

    async with factory() as session:
        document = await session.get(Document, document_id)
        if document is None:
            logger.info("Intelligence job skipped: document %s no longer exists.", document_id)
            return

        if not document.file_path:
            document.extraction_status = None
            await session.commit()
            return

        try:
            file_path = get_document_file_path(document)
        except ValueError as exc:
            document.extraction_status = STATUS_FAILED
            document.extraction_error = clip_error(str(exc))
            document.extracted_text = None
            document.extracted_char_count = None
            document.page_count = None
            document.tags = None
            document.summary = None
            document.summary_source = None
            document.extracted_at = datetime.now(UTC)
            await session.commit()
            return

        fingerprint = compute_file_fingerprint(file_path)
        if (
            not force
            and document.extraction_status == STATUS_COMPLETED
            and fingerprint is not None
            and document.content_fingerprint == fingerprint
        ):
            logger.debug("Intelligence job skipped: document %s already indexed.", document_id)
            return

        document.extraction_status = STATUS_PROCESSING
        document.extraction_error = None
        await session.commit()

        outcome = await asyncio.to_thread(
            extract_text_from_file,
            file_path,
            content_type=document.content_type,
            filename=document.original_filename,
            max_chars=settings.max_extracted_chars,
        )

        document.page_count = outcome.page_count
        document.content_fingerprint = fingerprint
        document.extracted_at = datetime.now(UTC)
        document.extraction_status = outcome.status

        if outcome.status == STATUS_COMPLETED:
            text = outcome.text
            tags = generate_tags(
                text=text,
                filename=document.original_filename,
            )
            summary, source = await generate_summary(text, title=document.name)
            document.extracted_text = text
            document.extracted_char_count = len(text)
            document.tags = tags
            document.summary = summary
            document.summary_source = source
            document.extraction_error = None
        else:
            document.extracted_text = None
            document.extracted_char_count = None
            document.tags = None
            document.summary = None
            document.summary_source = None
            document.extraction_error = clip_error(
                outcome.error or "Text extraction did not produce any text."
            )

        try:
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("Failed to persist intelligence for document %s.", document_id)


async def queue_document_intelligence(
    document_id: UUID,
    *,
    force: bool = False,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """Thin wrapper used by FastAPI background tasks (never raises)."""
    try:
        await run_document_intelligence(
            document_id,
            force=force,
            session_factory=session_factory,
        )
    except Exception as exc:
        # Last-resort guard: background tasks must not surface as 500s and
        # must never leave the document stuck in a non-terminal status.
        await _mark_failed(
            document_id,
            f"Unexpected error during extraction: {exc}",
            session_factory,
        )


async def _mark_failed(
    document_id: UUID,
    message: str,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> None:
    """Best-effort transition to the failed terminal status."""
    factory = session_factory or AsyncSessionLocal
    try:
        async with factory() as session:
            document = await session.get(Document, document_id)
            if document is None:
                return
            document.extraction_status = STATUS_FAILED
            document.extraction_error = clip_error(message)
            await session.commit()
    except Exception:
        logger.exception("Could not record extraction failure for document %s.", document_id)
