/**
 * Shared formatting helpers for document metadata.
 * Kept free of UI concerns so any view can reuse them.
 */

/**
 * Format a byte count into a human-readable string.
 * Returns an em dash for null/undefined (no file uploaded).
 */
export const formatFileSize = (bytes) => {
  if (bytes === null || bytes === undefined) return '—';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(2)} GB`;
};

/**
 * Format an ISO timestamp for display. Returns an em dash for missing values.
 */
export const formatDate = (isoString, { withTime = false } = {}) => {
  if (!isoString) return '—';
  const date = new Date(isoString);
  if (Number.isNaN(date.getTime())) return '—';
  return withTime ? date.toLocaleString() : date.toLocaleDateString();
};

/**
 * Whether a document record indicates a stored file is available.
 * Uses real metadata (original_filename / file_size), never file_path.
 */
export const hasStoredFile = (doc) =>
  Boolean(doc && (doc.original_filename || doc.file_size !== null && doc.file_size !== undefined));

/**
 * Best display name for a downloaded file: backend-suggested filename,
 * then the stored original filename, then the document name.
 */
export const getDocumentDisplayName = (doc) =>
  (doc && (doc.original_filename || doc.name)) || 'download';
