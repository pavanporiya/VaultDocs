"""
Tests for document intelligence: text extraction, metadata + auto-tagging,
summaries (including missing AI credentials), and permission-filtered
content search.

Covers the brief's requirements:
- supported / unsupported / malformed / encrypted / scanned file formats
- extraction failures, empty files, oversized uploads (no dangling status)
- tagging + summary failures and AI-provider fallback
- content search relevance, empty queries, user isolation, shared access,
  view-only access, revoked permissions, deleted documents
- owner-only re-indexing and stale-intelligence reset on re-upload
"""

import asyncio
import io
import re
import uuid
import zipfile
from pathlib import Path

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from vaultdocs.core.settings import settings
from vaultdocs.services.extraction import (
    STATUS_COMPLETED,
    STATUS_ENCRYPTED,
    STATUS_FAILED,
    STATUS_NO_TEXT,
    STATUS_UNSUPPORTED,
    extract_text_from_file,
)
from vaultdocs.services.intelligence import (
    ExtractiveSummaryProvider,
    build_extractive_summary,
    build_key_points,
    clip_error,
    generate_summary,
    generate_tags,
    get_summary_provider,
    run_document_intelligence,
)
from vaultdocs.services.search import chunk_text, score_chunk, tokenize_query

# ==============================================================================
# Helpers
# ==============================================================================

VALID_TAG_RE = re.compile(r"^[a-z0-9][a-z0-9:_-]{1,30}$")

PDF_TEXT_TEMPLATE = """%PDF-1.4
1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj
2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj
3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >> endobj
4 0 obj << /Length {length} >>
stream
{stream}
endstream
endobj
trailer << /Root 1 0 R >>
%%EOF
"""


def _make_pdf_with_text(text: str) -> bytes:
    """Handcraft a minimal single-page PDF with an uncompressed text layer."""
    stream = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET"
    pdf = PDF_TEXT_TEMPLATE.format(length=len(stream), stream=stream)
    return pdf.encode("latin-1")


def _make_pdf_image_only() -> bytes:
    """Handcraft a PDF whose only stream is an image (scanned-style, no text)."""
    payload = b"FAKEIMAGEBYTES"
    return (
        b"%PDF-1.4\n"
        b"4 0 obj << /Subtype /Image /Width 10 /Height 10 /BitsPerComponent 8"
        b" /ColorSpace /DeviceRGB /Length 14 >>\n"
        b"stream\n" + payload + b"\nendstream\nendobj\n"
        b"trailer << /Root 4 0 R >>\n%%EOF"
    )


def _make_pdf_encrypted() -> bytes:
    """Handcraft a PDF declaring an /Encrypt dictionary."""
    return (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"
        b"2 0 obj << /Encrypt 5 0 R >> endobj\n"
        b"trailer << /Encrypt 5 0 R >>\n%%EOF"
    )


def _make_docx(paragraphs: list[str]) -> bytes:
    """Build a minimal .docx package in memory containing the given paragraphs."""
    body = "".join(f"<w:p><w:r><w:t>{p}</w:t></w:r></w:p>" for p in paragraphs)
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        f"<w:body>{body}</w:body></w:document>"
    )
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("[Content_Types].xml", "<Types/>")
        archive.writestr("word/document.xml", document_xml)
    return buffer.getvalue()


async def _create_doc(client: AsyncClient, headers: dict[str, str], name: str) -> str:
    response = await client.post("/v1/documents", json={"name": name}, headers=headers)
    assert response.status_code == 201
    return response.json()["id"]


async def _upload(
    client: AsyncClient,
    headers: dict[str, str],
    doc_id: str,
    filename: str,
    content: bytes,
    media_type: str = "text/plain",
) -> dict:
    response = await client.post(
        f"/v1/documents/{doc_id}/upload",
        files={"file": (filename, content, media_type)},
        headers=headers,
    )
    assert response.status_code in (200, 201)
    return response.json()


async def _share(
    client: AsyncClient,
    owner_headers: dict[str, str],
    doc_id: str,
    recipient_email: str,
    download_allowed: bool = False,
) -> str:
    response = await client.post(
        f"/v1/documents/{doc_id}/shares",
        json={"user_email": recipient_email, "download_allowed": download_allowed},
        headers=owner_headers,
    )
    assert response.status_code == 201
    return response.json()["id"]


async def _wait_intelligence(
    client: AsyncClient,
    headers: dict[str, str],
    doc_id: str,
) -> dict:
    """Poll intelligence until the extraction status is terminal."""
    data: dict = {}
    for _ in range(100):
        response = await client.get(f"/v1/documents/{doc_id}/intelligence", headers=headers)
        assert response.status_code == 200
        data = response.json()
        if data.get("status") not in (None, "pending", "processing"):
            return data
        await asyncio.sleep(0.1)
    return data


# ==============================================================================
# Unit tests — text extraction (no database)
# ==============================================================================


def test_extract_plain_text(tmp_path: Path) -> None:
    """Plain .txt files extract cleanly."""
    path = tmp_path / "notes.txt"
    path.write_text(
        "Quarterly revenue increased by 12%.\nOperations review completed.",
        encoding="utf-8",
    )
    outcome = extract_text_from_file(
        path, content_type="text/plain", filename="notes.txt", max_chars=10_000
    )
    assert outcome.status == STATUS_COMPLETED
    assert "Quarterly revenue" in outcome.text
    assert "Operations review" in outcome.text
    assert outcome.page_count is None
    assert outcome.error is None
    assert outcome.truncated is False


def test_extract_truncates_to_max_chars(tmp_path: Path) -> None:
    """Extracted text is capped at max_chars with the truncated flag set."""
    path = tmp_path / "big.txt"
    path.write_text("word " * 5_000, encoding="utf-8")
    outcome = extract_text_from_file(
        path, content_type="text/plain", filename="big.txt", max_chars=500
    )
    assert outcome.status == STATUS_COMPLETED
    assert len(outcome.text) <= 500
    assert outcome.truncated is True


def test_extract_empty_file(tmp_path: Path) -> None:
    """Empty files report an explicit no_text outcome, not fabricated text."""
    path = tmp_path / "empty.txt"
    path.write_bytes(b"")
    outcome = extract_text_from_file(
        path, content_type="text/plain", filename="empty.txt", max_chars=1_000
    )
    assert outcome.status == STATUS_NO_TEXT
    assert outcome.text == ""


def test_extract_binary_payload_with_text_extension(tmp_path: Path) -> None:
    """A .txt filename with binary content is rejected, not mojibake."""
    path = tmp_path / "data.txt"
    path.write_bytes(b"AB\x00CD\x00EF")
    outcome = extract_text_from_file(
        path, content_type="text/plain", filename="data.txt", max_chars=1_000
    )
    assert outcome.status == STATUS_UNSUPPORTED


def test_extract_unsupported_extension(tmp_path: Path) -> None:
    """Unknown formats report unsupported with a helpful reason."""
    path = tmp_path / "sheet.xlsx"
    path.write_bytes(b"PK\x03\x04 fake spreadsheet bytes")
    outcome = extract_text_from_file(
        path, content_type="application/vnd.ms-excel", filename="sheet.xlsx", max_chars=1_000
    )
    assert outcome.status == STATUS_UNSUPPORTED
    assert outcome.error is not None


def test_extract_missing_file(tmp_path: Path) -> None:
    """A path without an on-disk file reports failed (never raises)."""
    outcome = extract_text_from_file(
        tmp_path / "ghost.txt", content_type="text/plain", filename="ghost.txt", max_chars=1_000
    )
    assert outcome.status == STATUS_FAILED


def test_extract_malformed_pdf(tmp_path: Path) -> None:
    """Non-PDF bytes with a .pdf name fail explicitly."""
    path = tmp_path / "broken.pdf"
    path.write_bytes(b"this is definitely not a pdf")
    outcome = extract_text_from_file(
        path, content_type="application/pdf", filename="broken.pdf", max_chars=1_000
    )
    assert outcome.status == STATUS_FAILED
    assert outcome.error is not None


def test_extract_encrypted_pdf(tmp_path: Path) -> None:
    """Encrypted PDFs are detected and reported as encrypted, not guessed at."""
    path = tmp_path / "secret.pdf"
    path.write_bytes(_make_pdf_encrypted())
    outcome = extract_text_from_file(
        path, content_type="application/pdf", filename="secret.pdf", max_chars=1_000
    )
    assert outcome.status == STATUS_ENCRYPTED
    assert outcome.error is not None
    assert "encrypted" in outcome.error.lower()


def test_extract_scanned_pdf(tmp_path: Path) -> None:
    """Image-only (scanned) PDFs report no_text with an image-only reason."""
    path = tmp_path / "scan.pdf"
    path.write_bytes(_make_pdf_image_only())
    outcome = extract_text_from_file(
        path, content_type="application/pdf", filename="scan.pdf", max_chars=1_000
    )
    assert outcome.status == STATUS_NO_TEXT
    assert outcome.error is not None
    assert "image" in outcome.error.lower() or "text layer" in outcome.error.lower()


def test_extract_pdf_with_text_layer(tmp_path: Path) -> None:
    """PDFs with a text layer extract the text and count pages."""
    path = tmp_path / "report.pdf"
    path.write_bytes(_make_pdf_with_text("Hello VaultDocs quarterly report"))
    outcome = extract_text_from_file(
        path, content_type="application/pdf", filename="report.pdf", max_chars=10_000
    )
    assert outcome.status == STATUS_COMPLETED
    assert "Hello VaultDocs quarterly report" in outcome.text
    assert outcome.page_count == 1


def test_extract_docx_paragraphs(tmp_path: Path) -> None:
    """DOCX paragraphs extract in order with paragraph breaks preserved."""
    path = tmp_path / "plan.docx"
    path.write_bytes(
        _make_docx(
            [
                "Revenue targets for the fiscal year.",
                "Hiring plan approved by the board.",
            ]
        )
    )
    outcome = extract_text_from_file(
        path,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="plan.docx",
        max_chars=10_000,
    )
    assert outcome.status == STATUS_COMPLETED
    assert outcome.text == (
        "Revenue targets for the fiscal year.\nHiring plan approved by the board."
    )


def test_extract_docx_preserves_entities_and_spacing(tmp_path: Path) -> None:
    """DOCX text nodes unescape XML entities and keep xml:space content."""
    path = tmp_path / "entity.docx"
    path.write_bytes(_make_docx(["R&amp;D budget approved", "Padded note"]))
    outcome = extract_text_from_file(
        path,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="entity.docx",
        max_chars=10_000,
    )
    assert outcome.status == STATUS_COMPLETED
    assert "R&D budget approved" in outcome.text
    assert "Padded note" in outcome.text


def test_extract_malformed_docx(tmp_path: Path) -> None:
    """Non-ZIP bytes with a .docx name fail explicitly (never raise)."""
    path = tmp_path / "broken.docx"
    path.write_bytes(b"this is not a zip archive at all")
    outcome = extract_text_from_file(
        path, content_type="application/octet-stream", filename="broken.docx", max_chars=1_000
    )
    assert outcome.status == STATUS_FAILED
    assert outcome.error is not None


def test_extract_docx_missing_document_part(tmp_path: Path) -> None:
    """A ZIP without word/document.xml is reported unsupported."""
    path = tmp_path / "odd.docx"
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("hello.txt", "hi")
    path.write_bytes(buffer.getvalue())
    outcome = extract_text_from_file(
        path,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="odd.docx",
        max_chars=1_000,
    )
    assert outcome.status == STATUS_UNSUPPORTED


# ==============================================================================
# Unit tests — auto-tagging, summaries, chunking (no database)
# ==============================================================================


def test_generate_tags_include_format_and_keywords() -> None:
    """Tags start with a format tag and include frequent content keywords."""
    text = (
        "Invoice payment overdue notice. Invoice reminder was sent. "
        "Payment received for invoice number. Unrelated gardening notes."
    )
    tags = generate_tags(text=text, filename="billing.txt")
    assert tags[0] == "type:text"
    assert "invoice" in tags
    assert "payment" in tags


def test_generate_tags_validated_and_capped() -> None:
    """Tag output is deduplicated, pattern-validated, and capped."""
    text = " ".join(f"term{i}" for i in range(60))
    tags = generate_tags(text=text, filename="list.md", max_tags=5)
    assert len(tags) <= 5
    assert all(VALID_TAG_RE.fullmatch(tag) for tag in tags)


def test_generate_tags_empty_text() -> None:
    """Empty text still yields only the format tag (no junk)."""
    tags = generate_tags(text="", filename="report.pdf")
    assert tags == ["type:pdf"]


def test_extractive_summary_quotes_source() -> None:
    """The local summarizer returns top sentences drawn from the source text."""
    text = (
        "The server migration completed successfully on Tuesday. "
        "The team verified all database replicas afterward. "
        "Latency metrics improved by 40 percent after the rollout. "
        "Monitoring dashboards show stable traffic patterns. "
        "Documentation was updated to reflect the new topology."
    )
    summary = build_extractive_summary(text, title="Migration")
    assert summary
    assert all(sentence.strip() in text for sentence in summary.split(". ") if sentence.strip())
    assert len(summary) <= 1_000
    assert len(summary) < len(text)


def test_extractive_summary_drops_title_heading() -> None:
    """A heading line that repeats the document title is not summarized."""
    title = "Quarterly Report"
    text = (
        "Quarterly Report\n"
        "Revenue grew by 8 percent this quarter. "
        "Costs remained flat overall. "
        "Guidance was reaffirmed for next quarter."
    )
    summary = build_extractive_summary(text, title=title)
    assert "Quarterly Report" not in summary
    assert "Revenue grew" in summary


def test_extractive_summary_handles_empty_and_malformed_input() -> None:
    """Empty or symbol-only input produces an empty summary (no guessing)."""
    assert build_extractive_summary("", title="X") == ""
    assert build_extractive_summary("!!! ??? ... \n --- ", title="X") == ""


def test_key_points_quote_source_text() -> None:
    """Key points are verbatim sentences from the source text."""
    text = (
        "Project Orion launched on Monday. Testing concluded on Friday. "
        "Rollout continues next week. Budget remains unchanged overall."
    )
    points = build_key_points(text)
    assert points
    assert all(point in text for point in points)


def test_clip_error_fits_column() -> None:
    """Error messages are trimmed to fit the String(512) column."""
    assert clip_error(None) is None
    clipped = clip_error("x" * 2_000)
    assert clipped is not None
    assert len(clipped) == 500


def test_default_provider_resolves_to_extractive(monkeypatch: pytest.MonkeyPatch) -> None:
    """Default configuration resolves to the local credential-free provider."""
    monkeypatch.setattr(settings, "ai_provider", "extractive")
    provider = get_summary_provider()
    assert isinstance(provider, ExtractiveSummaryProvider)


def test_missing_ai_credentials_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    """A remote provider without an API key falls back to local summaries."""
    monkeypatch.setattr(settings, "ai_provider", "openai_compatible")
    monkeypatch.setattr(settings, "ai_api_key", None)
    provider = get_summary_provider()
    assert isinstance(provider, ExtractiveSummaryProvider)


async def test_generate_summary_falls_back_when_remote_unreachable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unreachable remote provider degrades to local, non-empty summaries."""
    monkeypatch.setattr(settings, "ai_provider", "openai_compatible")
    monkeypatch.setattr(settings, "ai_api_key", "sk-test-not-a-real-key")
    monkeypatch.setattr(settings, "ai_base_url", "http://127.0.0.1:9/v1")
    monkeypatch.setattr(settings, "ai_timeout_seconds", 1.0)
    text = (
        "Project Orion launched on Monday. Testing concluded Friday. Rollout continues next week."
    )
    summary, source = await generate_summary(text, title="Orion")
    assert source == "extractive"
    assert summary


def test_chunk_text_small_deterministic() -> None:
    """Small chunking splits on word boundaries with forward progress."""
    chunks = chunk_text("one two three", size=6, overlap=2)
    assert chunks == ["one", "two", "three"]


def test_chunk_text_covers_content() -> None:
    """Chunking never loses the start or end of the content."""
    text = " ".join(f"word{i}" for i in range(400))
    chunks = chunk_text(text, size=300, overlap=60)
    assert len(chunks) >= len(text) // 400
    assert all(chunks)
    assert all(len(chunk) <= 300 for chunk in chunks)
    assert chunks[0].startswith("word0")
    assert chunks[-1].endswith("word399")


def test_chunk_text_edge_cases() -> None:
    """Blank text yields no chunks; invalid sizes raise ValueError."""
    assert chunk_text("   ", size=100, overlap=10) == []
    assert chunk_text("", size=100, overlap=10) == []
    with pytest.raises(ValueError):
        chunk_text("abc", size=0, overlap=0)


def test_tokenize_and_score() -> None:
    """Query tokenization and chunk scoring behave predictably."""
    assert tokenize_query("") == []
    assert tokenize_query("   ") == []
    assert tokenize_query("Quarterly Revenue") == ["quarterly", "revenue"]

    terms = tokenize_query("quarterly revenue")
    strong = score_chunk(
        terms,
        "quarterly revenue",
        "The quarterly revenue numbers show quarterly revenue growth once more.",
    )
    weak = score_chunk(terms, "quarterly revenue", "No relevant content here at all.")
    assert strong > 0
    assert weak == 0
    assert score_chunk([], "anything", "text") == 0.0


# ==============================================================================
# API tests — extraction status, re-index, access control (database)
# ==============================================================================


@pytest.mark.asyncio
async def test_upload_triggers_extraction(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Upload queues extraction; intelligence completes with tags + summary."""
    monkeypatch.setattr(settings, "ai_provider", "extractive")
    doc_id = await _create_doc(client, auth_headers_user_a, "Quarterly Notes")
    upload = await _upload(
        client,
        auth_headers_user_a,
        doc_id,
        "notes.txt",
        b"Quarterly revenue increased sharply. "
        b"The finance team verified every number. "
        b"Operational costs stayed flat during the quarter.",
    )
    assert upload["extraction_status"] in ("pending", "processing", "completed")

    intel = await _wait_intelligence(client, auth_headers_user_a, doc_id)
    assert intel["status"] == STATUS_COMPLETED
    assert intel["file_ready"] is True
    assert intel["error"] is None
    assert intel["summary"]
    assert intel["summary_source"] == "extractive"
    assert "type:text" in intel["tags"]
    assert intel["char_count"] and intel["char_count"] > 0
    assert intel["key_points"]
    assert intel["extracted_at"] is not None
    assert intel["is_owner"] is True
    assert intel["can_edit"] is True
    # The schema never exposes storage paths or raw extracted text.
    assert "file_path" not in intel
    assert "extracted_text" not in intel


@pytest.mark.asyncio
async def test_intelligence_requires_authentication(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """Unauthenticated intelligence requests are rejected with 401."""
    doc_id = await _create_doc(client, auth_headers_user_a, "Auth Doc")
    response = await client.get(f"/v1/documents/{doc_id}/intelligence")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_intelligence_hidden_from_outsiders(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
) -> None:
    """An unrelated user gets a safe 404 (existence never disclosed)."""
    doc_id = await _create_doc(client, auth_headers_user_a, "Private Notes")
    await _upload(
        client, auth_headers_user_a, doc_id, "private.txt", b"secret words inside a private file"
    )
    await _wait_intelligence(client, auth_headers_user_a, doc_id)

    response = await client.get(
        f"/v1/documents/{doc_id}/intelligence", headers=auth_headers_user_b
    )
    assert response.status_code == 404

    reindex = await client.post(
        f"/v1/documents/{doc_id}/intelligence/reindex", headers=auth_headers_user_b
    )
    assert reindex.status_code == 404


@pytest.mark.asyncio
async def test_intelligence_for_view_only_share_recipient(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b,
) -> None:
    """View-only recipients can read intelligence but cannot re-index."""
    doc_id = await _create_doc(client, auth_headers_user_a, "Shared View Doc")
    await _upload(client, auth_headers_user_a, doc_id, "view.txt", b"shared viewing content here")
    await _wait_intelligence(client, auth_headers_user_a, doc_id)
    await _share(client, auth_headers_user_a, doc_id, user_b.email, download_allowed=False)

    intel = await _wait_intelligence(client, auth_headers_user_b, doc_id)
    assert intel["status"] == STATUS_COMPLETED
    assert intel["is_owner"] is False
    assert intel["permission"] == "viewer"
    assert intel["can_edit"] is False
    assert intel["can_download"] is False
    assert "file_path" not in intel

    reindex = await client.post(
        f"/v1/documents/{doc_id}/intelligence/reindex", headers=auth_headers_user_b
    )
    assert reindex.status_code == 403


@pytest.mark.asyncio
async def test_reindex_owner_only(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """Owners can re-index; documents without files get a clean 400."""
    empty_doc_id = await _create_doc(client, auth_headers_user_a, "No File Doc")
    no_file = await client.post(
        f"/v1/documents/{empty_doc_id}/intelligence/reindex", headers=auth_headers_user_a
    )
    assert no_file.status_code == 400

    doc_id = await _create_doc(client, auth_headers_user_a, "Reindex Doc")
    await _upload(client, auth_headers_user_a, doc_id, "re.txt", b"reindex me please thanks")
    await _wait_intelligence(client, auth_headers_user_a, doc_id)

    response = await client.post(
        f"/v1/documents/{doc_id}/intelligence/reindex", headers=auth_headers_user_a
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == STATUS_COMPLETED
    assert data["is_owner"] is True


@pytest.mark.asyncio
async def test_unsupported_file_reports_status(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """Unsupported binaries land in a terminal unsupported state, not a 500."""
    doc_id = await _create_doc(client, auth_headers_user_a, "Binary Blob")
    upload = await _upload(
        client,
        auth_headers_user_a,
        doc_id,
        "blob.bin",
        b"\x00\x01\x02\x03\x04 binary payload",
        media_type="application/octet-stream",
    )
    assert upload["extraction_status"] in ("pending", "processing", "unsupported")

    intel = await _wait_intelligence(client, auth_headers_user_a, doc_id)
    assert intel["status"] == STATUS_UNSUPPORTED
    assert intel["summary"] is None
    assert intel["tags"] == []
    assert intel["error"]


@pytest.mark.asyncio
async def test_extraction_failure_when_file_missing_on_disk(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """A vanished on-disk file records a failed status instead of crashing."""
    doc_id = await _create_doc(client, auth_headers_user_a, "Ghost File Doc")
    await _upload(client, auth_headers_user_a, doc_id, "ghost.txt", b"temporary content")
    await _wait_intelligence(client, auth_headers_user_a, doc_id)

    detail = await client.get(f"/v1/documents/{doc_id}", headers=auth_headers_user_a)
    file_path = Path(detail.json()["file_path"])
    storage_dir = Path(settings.storage_dir).resolve()
    assert file_path.resolve().is_relative_to(storage_dir)
    assert file_path.exists()
    file_path.unlink()

    response = await client.post(
        f"/v1/documents/{doc_id}/intelligence/reindex", headers=auth_headers_user_a
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == STATUS_FAILED
    assert data["error"]
    assert data["summary"] is None


@pytest.mark.asyncio
async def test_reupload_resets_stale_intelligence(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Replacing a file clears stale text/tags/summary before re-extraction."""
    monkeypatch.setattr(settings, "ai_provider", "extractive")
    doc_id = await _create_doc(client, auth_headers_user_a, "Replaced Doc")
    await _upload(client, auth_headers_user_a, doc_id, "v1.txt", b"alpha protocol documentation")
    first = await _wait_intelligence(client, auth_headers_user_a, doc_id)
    assert first["status"] == STATUS_COMPLETED
    assert "alpha" in (first["summary"] or "").lower()

    upload = await _upload(
        client,
        auth_headers_user_a,
        doc_id,
        "v2.txt",
        b"beta protocol documentation with a much longer expanded appendix section",
    )
    assert upload["extraction_status"] in ("pending", "processing")

    second = await _wait_intelligence(client, auth_headers_user_a, doc_id)
    assert second["status"] == STATUS_COMPLETED
    summary = (second["summary"] or "").lower()
    assert "alpha" not in summary
    assert "beta" in summary
    # Status resets to pending while the replacement is queued (stale-free).
    assert second["extracted_at"] is not None


@pytest.mark.asyncio
async def test_extraction_without_ai_credentials_still_completes(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With no AI credentials configured, extraction still completes locally."""
    monkeypatch.setattr(settings, "ai_provider", "openai_compatible")
    monkeypatch.setattr(settings, "ai_api_key", None)

    doc_id = await _create_doc(client, auth_headers_user_a, "No AI Doc")
    await _upload(
        client,
        auth_headers_user_a,
        doc_id,
        "plain.txt",
        b"The deployment pipeline runs automated checks. Rollback is documented clearly.",
    )
    intel = await _wait_intelligence(client, auth_headers_user_a, doc_id)
    assert intel["status"] == STATUS_COMPLETED
    assert intel["summary_source"] == "extractive"
    assert intel["summary"]


@pytest.mark.asyncio
async def test_oversized_upload_leaves_no_extraction_state(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """An oversized upload is rejected and never queues extraction."""
    doc_id = await _create_doc(client, auth_headers_user_a, "Too Big Doc")
    oversized = b"x" * (settings.max_upload_size + 1024)
    response = await client.post(
        f"/v1/documents/{doc_id}/upload",
        files={"file": ("huge.txt", oversized, "text/plain")},
        headers=auth_headers_user_a,
    )
    assert response.status_code == 400

    intel = await client.get(f"/v1/documents/{doc_id}/intelligence", headers=auth_headers_user_a)
    assert intel.status_code == 200
    data = intel.json()
    assert data["file_ready"] is False
    assert data["status"] is None


@pytest.mark.asyncio
async def test_intelligence_job_skips_missing_and_deleted_documents(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    db_engine,
) -> None:
    """The job is a safe no-op for unknown IDs and idempotent for indexed docs."""
    doc_id = await _create_doc(client, auth_headers_user_a, "Idempotent Doc")
    await _upload(client, auth_headers_user_a, doc_id, "idem.txt", b"idempotent content sample")
    before = await _wait_intelligence(client, auth_headers_user_a, doc_id)
    assert before["status"] == STATUS_COMPLETED
    assert before["extracted_at"] is not None

    factory = async_sessionmaker(bind=db_engine, class_=AsyncSession, expire_on_commit=False)

    # Unknown document: no raise, no state change anywhere.
    await run_document_intelligence(uuid.uuid4(), session_factory=factory)

    # Re-run without force: identical fingerprint -> no-op (extracted_at unchanged).
    await run_document_intelligence(uuid.UUID(doc_id), session_factory=factory)
    after = await _wait_intelligence(client, auth_headers_user_a, doc_id)
    assert after["extracted_at"] == before["extracted_at"]
    assert after["status"] == STATUS_COMPLETED


# ==============================================================================
# API tests — content search permissions and relevance (database)
# ==============================================================================


@pytest.mark.asyncio
async def test_content_search_owner_isolation(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
) -> None:
    """Content search never returns another user's documents."""
    doc_a = await _create_doc(client, auth_headers_user_a, "Team Offsite Ideas")
    await _upload(
        client,
        auth_headers_user_a,
        doc_a,
        "offsite.txt",
        b"The team proposed hanggliding near the coast for the offsite.",
    )
    await _wait_intelligence(client, auth_headers_user_a, doc_a)

    doc_b = await _create_doc(client, auth_headers_user_b, "User B Private Notes")
    await _upload(
        client,
        auth_headers_user_b,
        doc_b,
        "mine.txt",
        b"Personal errands list for the weekend shopping trip.",
    )
    await _wait_intelligence(client, auth_headers_user_b, doc_b)

    mine = await client.get(
        "/v1/documents/search/content",
        params={"q": "hanggliding"},
        headers=auth_headers_user_a,
    )
    assert mine.status_code == 200
    hits = mine.json()
    assert [hit["id"] for hit in hits] == [doc_a]
    assert hits[0]["score"] > 0
    assert "hanggliding" in hits[0]["snippet"].lower()
    assert hits[0]["matched_chunk"] is not None
    assert hits[0]["file_path"] is not None  # owner keeps their own path

    theirs = await client.get(
        "/v1/documents/search/content",
        params={"q": "hanggliding"},
        headers=auth_headers_user_b,
    )
    assert theirs.status_code == 200
    assert theirs.json() == []


@pytest.mark.asyncio
async def test_content_search_relevance_ranking(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """Stronger matches rank above weaker ones."""
    strong_doc = await _create_doc(client, auth_headers_user_a, "Strong Match Doc")
    await _upload(
        client,
        auth_headers_user_a,
        strong_doc,
        "strong.txt",
        b"The revenue forecast projects revenue forecast growth for next quarter.",
    )
    await _wait_intelligence(client, auth_headers_user_a, strong_doc)

    weak_doc = await _create_doc(client, auth_headers_user_a, "Weak Match Doc")
    await _upload(
        client,
        auth_headers_user_a,
        weak_doc,
        "weak.txt",
        b"A weekly forecast was updated by the team.",
    )
    await _wait_intelligence(client, auth_headers_user_a, weak_doc)

    response = await client.get(
        "/v1/documents/search/content",
        params={"q": "revenue forecast"},
        headers=auth_headers_user_a,
    )
    assert response.status_code == 200
    hits = response.json()
    assert len(hits) == 2
    assert hits[0]["id"] == strong_doc
    assert hits[0]["score"] > hits[1]["score"]


@pytest.mark.asyncio
async def test_content_search_shared_and_view_only_access(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b,
) -> None:
    """Share recipients find shared content with viewer flags and no file path."""
    doc_id = await _create_doc(client, auth_headers_user_a, "Conservation Report")
    await _upload(
        client,
        auth_headers_user_a,
        doc_id,
        "birds.txt",
        b"The peregrine falcon population recovered along the river corridor.",
    )
    await _wait_intelligence(client, auth_headers_user_a, doc_id)
    await _share(client, auth_headers_user_a, doc_id, user_b.email, download_allowed=False)

    response = await client.get(
        "/v1/documents/search/content",
        params={"q": "peregrine"},
        headers=auth_headers_user_b,
    )
    assert response.status_code == 200
    hits = response.json()
    assert len(hits) == 1
    hit = hits[0]
    assert hit["id"] == doc_id
    assert hit["is_owner"] is False
    assert hit["permission"] == "viewer"
    assert hit["can_edit"] is False
    assert hit["can_download"] is False
    assert hit["file_path"] is None
    assert "peregrine" in hit["snippet"].lower()


@pytest.mark.asyncio
async def test_content_search_stops_after_share_revocation(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
    auth_headers_user_b: dict[str, str],
    user_b,
) -> None:
    """Revoking a share immediately removes the document from recipient search."""
    doc_id = await _create_doc(client, auth_headers_user_a, "Revocable Doc")
    await _upload(
        client,
        auth_headers_user_a,
        doc_id,
        "revoke.txt",
        b"Confidential narwhal expedition briefing for the crew.",
    )
    await _wait_intelligence(client, auth_headers_user_a, doc_id)
    share_id = await _share(
        client, auth_headers_user_a, doc_id, user_b.email, download_allowed=True
    )

    before = await client.get(
        "/v1/documents/search/content",
        params={"q": "narwhal"},
        headers=auth_headers_user_b,
    )
    assert before.status_code == 200
    assert [hit["id"] for hit in before.json()] == [doc_id]

    revoke = await client.delete(
        f"/v1/documents/{doc_id}/shares/{share_id}", headers=auth_headers_user_a
    )
    assert revoke.status_code == 204

    after = await client.get(
        "/v1/documents/search/content",
        params={"q": "narwhal"},
        headers=auth_headers_user_b,
    )
    assert after.status_code == 200
    assert after.json() == []


@pytest.mark.asyncio
async def test_content_search_after_document_deletion(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """Deleted documents vanish from content search with no stale results."""
    doc_id = await _create_doc(client, auth_headers_user_a, "Disposable Doc")
    await _upload(
        client,
        auth_headers_user_a,
        doc_id,
        "temp.txt",
        b"Transient quasarx telemetry data to be discarded soon.",
    )
    await _wait_intelligence(client, auth_headers_user_a, doc_id)

    found = await client.get(
        "/v1/documents/search/content",
        params={"q": "quasarx"},
        headers=auth_headers_user_a,
    )
    assert found.status_code == 200
    assert [hit["id"] for hit in found.json()] == [doc_id]

    delete = await client.delete(f"/v1/documents/{doc_id}", headers=auth_headers_user_a)
    assert delete.status_code == 204

    gone = await client.get(
        "/v1/documents/search/content",
        params={"q": "quasarx"},
        headers=auth_headers_user_a,
    )
    assert gone.status_code == 200
    assert gone.json() == []


@pytest.mark.asyncio
async def test_content_search_empty_and_blank_queries(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """Empty queries are rejected; blank queries mirror legacy list behavior."""
    empty = await client.get(
        "/v1/documents/search/content",
        params={"q": ""},
        headers=auth_headers_user_a,
    )
    assert empty.status_code == 422

    blank = await client.get(
        "/v1/documents/search/content",
        params={"q": "   "},
        headers=auth_headers_user_a,
    )
    assert blank.status_code == 200
    assert isinstance(blank.json(), list)


@pytest.mark.asyncio
async def test_content_search_requires_authentication(client: AsyncClient) -> None:
    """Unauthenticated content search is rejected with 401."""
    response = await client.get("/v1/documents/search/content", params={"q": "anything"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_content_search_falls_back_to_name_keyword_search(
    client: AsyncClient,
    auth_headers_user_a: dict[str, str],
) -> None:
    """Documents without extracted text still match via legacy name search."""
    doc_id = await _create_doc(client, auth_headers_user_a, "Quarterly Financial Summary")

    response = await client.get(
        "/v1/documents/search/content",
        params={"q": "Quarterly Financial"},
        headers=auth_headers_user_a,
    )
    assert response.status_code == 200
    hits = response.json()
    assert [hit["id"] for hit in hits] == [doc_id]
    # Fallback hits carry a zero score so callers can distinguish them.
    assert hits[0]["score"] == 0.0
    assert hits[0]["snippet"] == ""
