/**
 * File type classification for safe browser preview.
 *
 * Only formats that browsers render natively and reliably are marked
 * previewable. Everything else must show "Preview unavailable" + download.
 */

const PREVIEWABLE_IMAGE_TYPES = new Set([
  'image/png',
  'image/jpeg',
  'image/gif',
  'image/webp',
  'image/svg+xml',
  'image/bmp',
]);

const PREVIEWABLE_TEXT_TYPES = new Set([
  'text/plain',
  'text/markdown',
  'text/csv',
  'application/json',
]);

const EXTENSION_CONTENT_TYPES = {
  pdf: 'application/pdf',
  png: 'image/png',
  jpg: 'image/jpeg',
  jpeg: 'image/jpeg',
  gif: 'image/gif',
  webp: 'image/webp',
  svg: 'image/svg+xml',
  bmp: 'image/bmp',
  txt: 'text/plain',
  md: 'text/markdown',
  csv: 'text/csv',
  json: 'application/json',
};

/**
 * Resolve which preview renderer to use for a file.
 *
 * @param {string|null} contentType - Stored content_type metadata.
 * @param {string|null} filename - Original filename (fallback classification).
 * @returns {'pdf'|'image'|'text'|null} Preview kind, or null when unsupported.
 */
export const getPreviewKind = (contentType, filename) => {
  const type = (contentType || '').toLowerCase();

  if (type === 'application/pdf') return 'pdf';
  if (PREVIEWABLE_IMAGE_TYPES.has(type)) return 'image';
  if (PREVIEWABLE_TEXT_TYPES.has(type)) return 'text';

  // Fall back to the file extension when content_type is generic or missing.
  const extension = (filename || '').split('.').pop()?.toLowerCase();
  const extensionType = extension ? EXTENSION_CONTENT_TYPES[extension] : null;
  if (extensionType) return getPreviewKind(extensionType, null);

  return null;
};

/**
 * Maximum byte size for rendering text previews inline.
 * Larger files get a "too large to preview" notice instead.
 */
export const MAX_TEXT_PREVIEW_BYTES = 1024 * 1024; // 1 MB
