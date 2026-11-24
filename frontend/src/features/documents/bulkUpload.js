/**
 * Bulk upload utilities: multi-file + full-folder upload.
 *
 * Design notes (zero backend changes):
 * - Reuses the existing APIs only:
 *     GET/POST /folders        → resolve/create nested folder hierarchy
 *     POST /documents          → create the document record (name, folder_id)
 *     POST /documents/{id}/upload → stream the file bytes (existing validation:
 *                                   auth, owner-only, size cap, extraction)
 * - The backend never overwrites an existing document: every queued file gets
 *   its OWN newly-created document record, so an existing document with the
 *   same name is never touched. Duplicate names are allowed by the schema, so
 *   conflicts are safe (no silent overwrite, no silent skip).
 * - Path safety: every folder/file segment is sanitized client-side (no
 *   absolute paths, no `..`, no empty segments, control chars stripped). The
 *   backend is defense-in-depth: folders validate parent ownership + cycles,
 *   document storage paths are UUID-based inside storage_dir.
 * - Known limitation: `webkitdirectory` FileLists do NOT include empty
 *   subfolders, so empty folders cannot be created via folder upload.
 *   (Documented; no schema support needed.)
 */

/**
 * Sanitize a single path segment (folder name or filename).
 * Returns null when the segment is unusable after cleaning.
 */
export const sanitizeSegment = (segment) => {
  if (typeof segment !== 'string') return null;
  // Strip control chars, surrounding whitespace, and path separators.
  let cleaned = segment
    // eslint-disable-next-line no-control-regex
    .replace(/[\u0000-\u001f\u007f]/g, '')
    .replace(/[/\\]/g, '')
    .trim();
  // Never allow traversal or hidden-parent references as literal names.
  if (cleaned === '' || cleaned === '.' || cleaned === '..') return null;
  if (cleaned.length > 255) cleaned = cleaned.slice(0, 255);
  return cleaned;
};

/**
 * Derive the sanitized relative path for an entry in a FileList.
 *
 * Uses `webkitRelativePath` (folder picker) and falls back to `name`
 * (single/multi file picker). Returns { segments, filename } or null when
 * the entry is unsafe/empty.
 */
export const parseEntryPath = (file) => {
  if (!file) return null;
  const raw = typeof file.webkitRelativePath === 'string' && file.webkitRelativePath
    ? file.webkitRelativePath
    : file.name;
  if (!raw) return null;

  const parts = String(raw).split(/[/\\]+/).filter((p) => p !== '');
  if (parts.length === 0) return null;

  const filename = sanitizeSegment(parts[parts.length - 1]);
  if (!filename) return null;

  const segments = parts.slice(0, -1).map(sanitizeSegment);
  // Any segment failed sanitization → reject the whole entry (traversal etc).
  if (segments.some((s) => s === null)) return null;

  return { segments, filename };
};

/**
 * Map of "parentKey/segmentName" → folder id, seeded from the user's existing
 * folders, so identical paths reuse existing folders instead of duplicating.
 */
export const buildFolderCache = (folders) => {
  const cache = new Map();
  (folders || []).forEach((f) => {
    if (!f || !f.id) return;
    const name = sanitizeSegment(f.name);
    if (!name) return;
    const key = `${f.parent_id || 'root'}/${name}`;
    // First one wins on sibling name collisions (backend allows duplicates).
    if (!cache.has(key)) cache.set(key, f.id);
  });
  return cache;
};

/**
 * Resolve (create-or-reuse) a folder chain. Returns the final folder id, or
 * null for root. Sequential per level; uses the shared cache so a batch with
 * many files in the same folders creates each folder exactly once.
 */
export const resolveFolderPath = async (api, segments, cache) => {
  let parentId = null;
  for (const name of segments) {
    const key = `${parentId || 'root'}/${name}`;
    let folderId = cache.get(key);
    if (!folderId) {
      // eslint-disable-next-line no-await-in-loop
      const created = await api.post('/folders', { name, parent_id: parentId });
      folderId = created.id;
      cache.set(key, folderId);
    }
    parentId = folderId;
  }
  return parentId;
};

/**
 * Upload one parsed entry: ensure folders → create document → upload bytes.
 * Throws on any failure; callers (the queue) capture the error per-file.
 * `onProgress` receives 0..100 byte progress for the file transfer step.
 */
export const uploadEntry = async ({ api, uploadFn, folderCache, entry, onProgress }) => {
  const folder_id = await resolveFolderPath(api, entry.segments, folderCache);

  const doc = await api.post('/documents', { name: entry.filename, folder_id });

  const formData = new FormData();
  formData.append('file', entry.file, entry.filename);

  const updated = await uploadFn(
    `/documents/${doc.id}/upload`,
    formData,
    typeof onProgress === 'function' ? onProgress : undefined
  );

  return updated || doc;
};

/**
 * Minimal status-machine queue runner.
 *
 * - Concurrency limit (default 3) keeps large batches polite.
 * - Per-file status: pending → uploading → done | error.
 * - `retryFailed()` re-runs ONLY files in error state; completed files are
 *   never re-uploaded (no duplicate documents).
 * - Entries that fail folder-creation/document-creation steps restart from
 *   the beginning for that file only; the folder cache makes that idempotent.
 *
 * Returns { snapshot, run, retryFailed, cancel } control functions. State
 * changes are reported through onStateChange(snapshotArray).
 */
export const createUploadQueue = ({
  entries,
  api,
  uploadFn,
  concurrency = 3,
  onStateChange = null,
  initialFolderCache = null,
}) => {
  const items = (entries || []).map((entry, index) => ({
    id: index,
    entry,
    status: 'pending', // pending | uploading | done | error
    progress: 0,
    error: null,
    documentId: null,
  }));

  // Seed from the user's existing folders so identical paths are REUSED,
  // never duplicated (callers pass buildFolderCache(await api.get('/folders'))).
  const folderCache = initialFolderCache instanceof Map ? initialFolderCache : new Map();
  let cancelled = false;

  const snapshot = () => items.map((i) => ({ ...i }));
  const notify = () => {
    if (typeof onStateChange === 'function') onStateChange(snapshot());
  };

  const processItem = async (item) => {
    item.status = 'uploading';
    item.progress = 0;
    item.error = null;
    notify();
    try {
      // eslint-disable-next-line no-await-in-loop
      const doc = await uploadEntry({
        api,
        uploadFn,
        folderCache,
        entry: item.entry,
        onProgress: (pct) => {
          item.progress = pct;
          notify();
        },
      });
      item.documentId = doc?.id || null;
      item.status = 'done';
      item.progress = 100;
    } catch (err) {
      item.status = 'error';
      item.error = err?.message || 'Upload failed.';
    }
    notify();
  };

  const runBatch = async (targets) => {
    const queue = [...targets];
    const workers = Array.from(
      { length: Math.max(1, Math.min(concurrency, queue.length)) },
      async () => {
        while (!cancelled && queue.length > 0) {
          const item = queue.shift();
          // eslint-disable-next-line no-await-in-loop
          await processItem(item);
        }
      }
    );
    await Promise.all(workers);
  };

  return {
    snapshot,
    cancel: () => {
      cancelled = true;
    },
    run: () => runBatch(items.filter((i) => i.status === 'pending')),
    retryFailed: () => runBatch(items.filter((i) => i.status === 'error')),
  };
};
