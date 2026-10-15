"""
Text extraction for uploaded documents.

Design constraints (see docs/PROJECT_PROGRESS.md):

- Uploaded content is treated strictly as data: it is never executed,
  imported, rendered, or handed to a shell. Parsing operates on raw bytes
  using the standard library only — no third-party document parser is
  installed in this environment, and no dependency was added without the
  compatibility check / approval the project rules require.
- Every outcome is explicit (completed / unsupported / encrypted / no_text /
  failed) so callers surface honest status instead of guessing.
- Encrypted PDFs and scanned/image-only PDFs are detected and reported
  explicitly rather than returning fabricated text. OCR is intentionally not
  wired up: no OCR binary or Python package is available here (documented
  blocker).
"""

from __future__ import annotations

import io
import re
import zipfile
import zlib
from dataclasses import dataclass
from html import unescape as html_unescape
from pathlib import Path

# ------------------------------------------------------------------------------
# Extraction statuses (persisted on documents.extraction_status)
# ------------------------------------------------------------------------------

STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_UNSUPPORTED = "unsupported"
STATUS_ENCRYPTED = "encrypted"
STATUS_NO_TEXT = "no_text"
STATUS_FAILED = "failed"

#: Terminal statuses — no background work is outstanding.
TERMINAL_STATUSES = frozenset(
    {STATUS_COMPLETED, STATUS_UNSUPPORTED, STATUS_ENCRYPTED, STATUS_NO_TEXT, STATUS_FAILED}
)

#: Statuses that mean a background job should be (re)queued.
RUNNABLE_STATUSES = frozenset({STATUS_PENDING, STATUS_PROCESSING, None})

# ------------------------------------------------------------------------------
# Format maps
# ------------------------------------------------------------------------------

DOCX_MEDIA_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
PDF_MEDIA_TYPE = "application/pdf"

#: Plain-text-ish formats decoded directly from bytes.
TEXT_EXTENSIONS = frozenset(
    {".txt", ".md", ".markdown", ".csv", ".tsv", ".log", ".json", ".yaml", ".yml", ".ini", ".cfg"}
)

#: Text media types that fall back to plain decoding even without a known extension.
TEXT_MEDIA_TYPES = frozenset(
    {"application/json", "application/yaml", "application/x-yaml", "application/xml"}
)

#: Hard cap on bytes read for extraction (defensive; upload cap is smaller).
MAX_EXTRACTION_BYTES = 25 * 1024 * 1024

#: Hard cap on the inflated size of a single PDF stream (decompression bomb guard).
MAX_PDF_STREAM_OUT = 8 * 1024 * 1024

#: Hard cap on the uncompressed size of a DOCX document part (zip bomb guard).
MAX_DOCX_XML_BYTES = 32 * 1024 * 1024

#: Minimum ratio of printable characters for PDF stream text to be kept.
MIN_PRINTABLE_RATIO = 0.7


@dataclass(frozen=True, slots=True)
class ExtractionOutcome:
    """Result of a single extraction attempt. Never raises for bad input."""

    status: str
    text: str = ""
    page_count: int | None = None
    error: str | None = None
    truncated: bool = False


# ------------------------------------------------------------------------------
# Public entry point
# ------------------------------------------------------------------------------


def extract_text_from_file(
    file_path: Path,
    *,
    content_type: str | None,
    filename: str | None,
    max_chars: int,
) -> ExtractionOutcome:
    """
    Extract text from a stored document file.

    Dispatch is based on the original filename extension and the declared
    MIME type, then verified against magic bytes. Malformed, oversized,
    binary, encrypted, and unsupported inputs all return an explicit
    ``ExtractionOutcome`` — this function never raises for bad content.
    """
    if not file_path.is_file():
        return ExtractionOutcome(status=STATUS_FAILED, error="File not found on disk.")

    try:
        file_size = file_path.stat().st_size
    except OSError as exc:
        return ExtractionOutcome(status=STATUS_FAILED, error=f"Could not stat file: {exc}")

    if file_size == 0:
        return ExtractionOutcome(
            status=STATUS_NO_TEXT,
            error="File is empty; nothing to extract.",
        )

    if file_size > MAX_EXTRACTION_BYTES:
        return ExtractionOutcome(
            status=STATUS_UNSUPPORTED,
            error="File is too large for text extraction.",
        )

    try:
        data = file_path.read_bytes()
    except OSError as exc:
        return ExtractionOutcome(status=STATUS_FAILED, error=f"Could not read file: {exc}")

    extension = Path(filename or file_path.name).suffix.lower()
    media = (content_type or "").lower().split(";")[0].strip()

    if extension == ".pdf" or media == PDF_MEDIA_TYPE:
        return _extract_pdf(data, max_chars=max_chars)

    if extension == ".docx" or media == DOCX_MEDIA_TYPE:
        return _extract_docx(data, max_chars=max_chars)

    if extension in TEXT_EXTENSIONS or media.startswith("text/") or media in TEXT_MEDIA_TYPES:
        return _extract_plain_text(data, max_chars=max_chars)

    return ExtractionOutcome(
        status=STATUS_UNSUPPORTED,
        error=f"Unsupported file type for extraction ({extension or media or 'unknown'}).",
    )


# ------------------------------------------------------------------------------
# Plain text
# ------------------------------------------------------------------------------


def _extract_plain_text(data: bytes, *, max_chars: int) -> ExtractionOutcome:
    """Decode a text-format payload. Binary payloads are rejected explicitly."""
    if b"\x00" in data[:100_000]:
        return ExtractionOutcome(
            status=STATUS_UNSUPPORTED,
            error="File content is binary; text extraction skipped.",
        )

    return _finalize(_decode_bytes(data), max_chars=max_chars)


def _decode_bytes(data: bytes) -> str:
    """Decode bytes with increasingly permissive encodings; never raises."""
    for encoding in ("utf-8-sig", "utf-8", "cp1252"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("latin-1", errors="replace")


def _finalize(
    text: str,
    *,
    max_chars: int,
    page_count: int | None = None,
    empty_status: str = STATUS_COMPLETED,
    empty_error: str | None = None,
) -> ExtractionOutcome:
    """Normalize, cap, and wrap extracted text into an outcome."""
    cleaned = _normalize_text(text)
    truncated = False
    if len(cleaned) > max_chars:
        cleaned = cleaned[:max_chars].rstrip()
        truncated = True

    if not cleaned:
        return ExtractionOutcome(
            status=empty_status,
            text="",
            page_count=page_count,
            error=empty_error,
            truncated=truncated,
        )

    return ExtractionOutcome(
        status=STATUS_COMPLETED,
        text=cleaned,
        page_count=page_count,
        truncated=truncated,
    )


def _normalize_text(text: str) -> str:
    """Strip control noise, keep indentation, collapse blank-line runs."""
    normalized = text.replace("\x00", " ").replace("\r\n", "\n").replace("\r", "\n")

    lines: list[str] = []
    pending_blank = False
    for raw_line in normalized.split("\n"):
        line = raw_line.rstrip()
        if not line.strip():
            pending_blank = bool(lines)
            continue
        if pending_blank:
            lines.append("")
            pending_blank = False
        lines.append(line)

    return "\n".join(lines).strip()


# ------------------------------------------------------------------------------
# DOCX (OOXML) — zip + targeted regex over word/document.xml
# ------------------------------------------------------------------------------
#
# WordprocessingML is handled with regex over the already-decoded XML string
# instead of an XML parser: the stdlib xml.etree import is flagged by
# Ruff's bandit rules (S405/S314) and untrusted XML parsing libraries are not
# installed. Only <w:t> text nodes are collected; markup is never evaluated.

_W_TAG_RE = re.compile(r"<[^>]+>")
_W_T_OPEN_RE = re.compile(r"^<w:t(?:\s[^>]*)?>$")
_W_T_CLOSE_RE = re.compile(r"^</w:t\s*>$")


def _extract_docx(data: bytes, *, max_chars: int) -> ExtractionOutcome:
    """Extract paragraph text from a .docx package."""
    if not zipfile.is_zipfile(io.BytesIO(data)):
        return ExtractionOutcome(
            status=STATUS_FAILED,
            error="Malformed DOCX file (not a valid ZIP archive).",
        )

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            if "word/document.xml" not in archive.namelist():
                return ExtractionOutcome(
                    status=STATUS_UNSUPPORTED,
                    error="Unsupported DOCX package (missing word/document.xml).",
                )

            info = archive.getinfo("word/document.xml")
            if info.file_size > MAX_DOCX_XML_BYTES:
                return ExtractionOutcome(
                    status=STATUS_UNSUPPORTED,
                    error="DOCX document part is too large for extraction.",
                )

            with archive.open(info) as member:
                xml_bytes = member.read(MAX_DOCX_XML_BYTES + 1)
    except (zipfile.BadZipFile, RuntimeError, NotImplementedError, KeyError, OSError) as exc:
        return ExtractionOutcome(
            status=STATUS_FAILED,
            error=f"Malformed DOCX file ({type(exc).__name__}).",
        )
    except zlib.error:
        return ExtractionOutcome(status=STATUS_FAILED, error="Malformed DOCX file (corrupt part).")

    xml_text = _decode_bytes(xml_bytes)
    return _finalize(
        _docx_xml_to_text(xml_text),
        max_chars=max_chars,
        empty_status=STATUS_NO_TEXT,
        empty_error="Document contains no extractable text.",
    )


def _docx_xml_to_text(xml_text: str) -> str:
    """Collect <w:t> text nodes in document order, marking paragraph breaks."""
    parts: list[str] = []
    in_text_element = 0
    cursor = 0

    for match in _W_TAG_RE.finditer(xml_text):
        between = xml_text[cursor : match.start()]
        if in_text_element and between:
            parts.append(html_unescape(between))

        tag = match.group(0)
        if _W_T_OPEN_RE.match(tag):
            in_text_element += 1
        elif _W_T_CLOSE_RE.match(tag):
            in_text_element = max(0, in_text_element - 1)
        elif _is_break_tag(tag):
            parts.append("\n")

        cursor = match.end()

    return "".join(parts)


def _is_break_tag(tag: str) -> bool:
    """True for paragraph/row boundaries, tabs, and line breaks only.

    Prefix boundaries are checked so that ``</w:pPr>`` or ``<w:tbl>`` are not
    mistaken for ``</w:p>`` / ``<w:tab/>``.
    """
    for prefix, boundary in (
        ("</w:p", "> "),
        ("</w:tr", "> "),
        ("</w:tc", "> "),
        ("<w:tab", "/> "),
        ("<w:br", "/> "),
        ("<w:cr", "/> "),
    ):
        if tag.startswith(prefix):
            rest = tag[len(prefix) :]
            return not rest or rest[0] in boundary
    return False


# ------------------------------------------------------------------------------
# PDF — minimal stdlib text-layer extraction
# ------------------------------------------------------------------------------

_PDF_HEADER = b"%PDF-"
_PDF_PAGE_RE = re.compile(rb"/Type\s*/Page(?![A-Za-z])")
_PDF_ENCRYPT_RE = re.compile(rb"/Encrypt\s+\d+\s+\d+\s+R")
_PDF_IMAGE_RE = re.compile(rb"/Subtype\s*/Image")
_PDF_STREAM_RE = re.compile(rb"stream\r?\n(.*?)endstream", re.DOTALL)
_INLINE_IMAGE_END_RE = re.compile(rb"\sEI(?=[\s\)\]/<>])")

_PDF_WS = b"\x00\t\n\x0c\r "
_PDF_DELIMS = b"()<>[]{}/%"


def _extract_pdf(data: bytes, *, max_chars: int) -> ExtractionOutcome:
    """Extract the text layer of a PDF. Encrypted and scanned PDFs are explicit."""
    if _PDF_HEADER not in data[:1024]:
        return ExtractionOutcome(
            status=STATUS_FAILED,
            error="Not a valid PDF file (missing %PDF header).",
        )

    page_count = len(_PDF_PAGE_RE.findall(data)) or None

    if _PDF_ENCRYPT_RE.search(data) is not None:
        return ExtractionOutcome(
            status=STATUS_ENCRYPTED,
            page_count=page_count,
            error="PDF is encrypted; text extraction requires the password.",
        )

    fragments: list[str] = []
    for match in _PDF_STREAM_RE.finditer(data):
        raw_stream = match.group(1).rstrip(b"\r\n")
        content = _try_inflate(raw_stream)
        if content is None:
            content = raw_stream
        if b"BT" not in content:
            continue

        text = _pdf_content_to_text(content)
        if text and _printable_ratio(text) >= MIN_PRINTABLE_RATIO:
            fragments.append(text)

    text = "\n".join(fragments)
    if not text.strip():
        scanned = _PDF_IMAGE_RE.search(data) is not None
        return ExtractionOutcome(
            status=STATUS_NO_TEXT,
            page_count=page_count,
            error=(
                "PDF appears to be scanned or image-only (no text layer)."
                if scanned
                else "No extractable text layer found in PDF."
            ),
        )

    return _finalize(text, max_chars=max_chars, page_count=page_count)


def _try_inflate(data: bytes) -> bytes | None:
    """Best-effort FlateDecode (zlib/raw-deflate) decompression with size cap."""
    for wbits in (zlib.MAX_WBITS, -zlib.MAX_WBITS):
        try:
            decompressor = zlib.decompressobj(wbits)
            out = decompressor.decompress(data, MAX_PDF_STREAM_OUT)
            if decompressor.unconsumed_tail:
                return None
            out += decompressor.flush()
            return out
        except zlib.error:
            continue
    return None


def _printable_ratio(text: str) -> float:
    """Fraction of printable characters (used to drop binary-garbage streams)."""
    if not text:
        return 0.0
    printable = sum(1 for ch in text if ch.isprintable() or ch in "\n\t")
    return printable / len(text)


def _read_literal_string(buf: bytes, start: int) -> tuple[bytes, int]:
    """Read a PDF literal string ``(...)`` starting at ``start`` (on the ``(``).

    Handles nesting, backslash escapes (including octal) and line
    continuations. Returns the raw bytes and the index after the closing
    parenthesis.
    """
    out = bytearray()
    depth = 0
    index = start + 1
    total = len(buf)

    while index < total:
        byte = buf[index]

        if byte == 0x5C:  # backslash escape
            index += 1
            if index >= total:
                break
            escape = buf[index]
            if escape == 0x6E:  # \n
                out.append(0x0A)
            elif escape == 0x72:  # \r
                out.append(0x0D)
            elif escape == 0x74:  # \t
                out.append(0x09)
            elif escape == 0x62:  # \b
                out.append(0x08)
            elif escape == 0x66:  # \f
                out.append(0x0C)
            elif escape in (0x28, 0x29, 0x5C):  # \( \) \\
                out.append(escape)
            elif 0x30 <= escape <= 0x37:  # octal escape
                digits = chr(escape)
                index += 1
                while index < total and len(digits) < 3 and 0x30 <= buf[index] <= 0x37:
                    digits += chr(buf[index])
                    index += 1
                out.append(int(digits, 8) & 0xFF)
                continue
            elif escape == 0x0D:  # line continuation
                if index + 1 < total and buf[index + 1] == 0x0A:
                    index += 1
            elif escape == 0x0A:  # line continuation
                pass
            else:
                out.append(escape)
            index += 1
            continue

        if byte == 0x28:  # nested opening paren
            depth += 1
            out.append(byte)
        elif byte == 0x29:  # closing paren
            if depth == 0:
                index += 1
                break
            depth -= 1
            out.append(byte)
        else:
            out.append(byte)

        index += 1

    return bytes(out), index


def _read_hex_string(buf: bytes, start: int) -> tuple[bytes, int]:
    """Read a PDF hex string ``<...>`` starting at ``start`` (on the ``<``)."""
    end = buf.find(b">", start + 1)
    if end == -1:
        return b"", len(buf)

    hex_chars = re.sub(rb"[^0-9A-Fa-f]", b"", buf[start + 1 : end])
    if len(hex_chars) % 2:
        hex_chars = hex_chars[:-1]
    try:
        return bytes.fromhex(hex_chars.decode("ascii")), end + 1
    except ValueError:
        return b"", end + 1


def _decode_pdf_string(raw: bytes) -> str:
    """Decode PDF string bytes (UTF-16 with BOM, UTF-16BE heuristic, else WinAnsi)."""
    if raw.startswith((b"\xfe\xff", b"\xff\xfe")):
        return raw.decode("utf-16", errors="replace")

    even = raw[1::2]
    if len(raw) >= 4 and even and even.count(0) > len(even) // 2:
        return raw.decode("utf-16-be", errors="replace")

    return raw.decode("cp1252", errors="replace")


def _pdf_content_to_text(content: bytes) -> str:
    """Walk a PDF page-content stream and collect text-showing operands.

    Text positioning operators (Td/TD/Tm/T*/ET) become newlines; TJ kerning
    arrays widen on large negative adjustments; inline images (BI..EI) are
    skipped. This is a best-effort text-layer reader, not a layout engine.
    """
    parts: list[str] = []
    index = 0
    total = len(content)

    while index < total:
        byte = content[index]

        if byte == 0x28:  # literal string
            raw, index = _read_literal_string(content, index)
            parts.append(_decode_pdf_string(raw))
        elif byte == 0x3C:  # '<'
            if index + 1 < total and content[index + 1] == 0x3C:  # dict start
                index += 2
            else:
                raw, index = _read_hex_string(content, index)
                parts.append(_decode_pdf_string(raw))
        elif byte == 0x5B:  # TJ array
            index = _consume_tj_array(content, index, parts)
        elif byte == 0x25:  # comment
            newline = content.find(b"\n", index)
            index = total if newline == -1 else newline + 1
        elif byte == 0x2F:  # name object (/F1, /Helvetica, ...)
            index += 1
            while (
                index < total
                and content[index] not in _PDF_WS
                and content[index] not in _PDF_DELIMS
            ):
                index += 1
        elif byte in _PDF_WS or byte in _PDF_DELIMS:
            index += 1
        else:
            end = index
            while end < total and content[end] not in _PDF_WS and content[end] not in _PDF_DELIMS:
                end += 1
            if end == index:
                index += 1
                continue

            word = content[index:end]
            if word in (b"'", b'"'):
                # The string operand precedes the operator: start a new line
                # just before the operand that was already appended.
                if parts and parts[-1] != "\n":
                    parts.insert(len(parts) - 1, "\n")
            elif word in (b"Td", b"TD", b"Tm", b"T*", b"ET", b"BT"):
                parts.append("\n")
            elif word == b"BI":
                skip = _INLINE_IMAGE_END_RE.search(content, end)
                if skip is None:
                    break
                index = skip.end()
                continue

            index = end

    return "".join(parts)


def _consume_tj_array(buf: bytes, start: int, parts: list[str]) -> int:
    """Consume a ``TJ`` array starting at ``[``; append strings and gaps to ``parts``."""
    index = start + 1
    total = len(buf)

    while index < total:
        byte = buf[index]

        if byte == 0x5D:  # ']'
            return index + 1

        if byte == 0x28:
            raw, index = _read_literal_string(buf, index)
            parts.append(_decode_pdf_string(raw))
        elif byte == 0x3C:
            if index + 1 < total and buf[index + 1] == 0x3C:
                index += 2
            else:
                raw, index = _read_hex_string(buf, index)
                parts.append(_decode_pdf_string(raw))
        elif byte == 0x5B:
            index = _consume_tj_array(buf, index, parts)
        elif byte in _PDF_WS or byte in _PDF_DELIMS:
            index += 1
        else:
            end = index
            while end < total and buf[end] not in _PDF_WS and buf[end] not in _PDF_DELIMS:
                end += 1
            if end == index:
                index += 1
                continue

            token = buf[index:end]
            index = end
            try:
                value = float(token.decode("latin-1"))
            except ValueError:
                continue
            if value <= -150:  # wide kerning gap ~ one space or more
                parts.append(" ")

    return total
