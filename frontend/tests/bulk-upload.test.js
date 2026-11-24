/**
 * Regression tests for bulk (multi-file + folder) upload utilities.
 *
 * Covers the Phase 3 checklist items that are automatable without a browser:
 * - Nested folder structure preserved (relative paths).
 * - Same filename in different folders handled correctly.
 * - Existing folders REUSED (never duplicated) via seeded cache.
 * - Path traversal attempts (`..`, absolute, separators) rejected.
 * - Per-file failures isolated; retry re-runs ONLY failed files
 *   (successful files never re-uploaded → no duplicate documents).
 * - Concurrency-limited queue processes every entry exactly once.
 *
 * Network layer is mocked in-process — no live server.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

import {
  buildFolderCache,
  createUploadQueue,
  parseEntryPath,
  resolveFolderPath,
  sanitizeSegment,
  uploadEntry,
} from '../src/features/documents/bulkUpload';

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const mkFile = (name, relativePath = '') => {
  const blob = new Blob(['x'], { type: 'text/plain' });
  // `size` is a getter-only on Blob — the 1-byte body defines it.
  return Object.assign(blob, {
    name,
    webkitRelativePath: relativePath,
  });
};

const entryFor = (name, relativePath = '') => {
  const file = mkFile(name, relativePath);
  const parsed = parseEntryPath(file);
  return { file, ...parsed, size: file.size };
};

// ---------------------------------------------------------------------------
// sanitizeSegment
// ---------------------------------------------------------------------------

describe('sanitizeSegment', () => {
  it('keeps normal names', () => {
    expect(sanitizeSegment('Reports 2026')).toBe('Reports 2026');
  });

  it('rejects traversal and dot segments', () => {
    expect(sanitizeSegment('..')).toBeNull();
    expect(sanitizeSegment('.')).toBeNull();
    expect(sanitizeSegment('')).toBeNull();
    expect(sanitizeSegment('   ')).toBeNull();
    expect(sanitizeSegment(null)).toBeNull();
  });

  it('strips separators instead of creating nested paths from a single segment', () => {
    expect(sanitizeSegment('a/b')).toBe('ab');
    expect(sanitizeSegment('a\\b')).toBe('ab');
  });

  it('truncates overlong names to 255 chars', () => {
    expect(sanitizeSegment('x'.repeat(300)).length).toBe(255);
  });
});

// ---------------------------------------------------------------------------
// parseEntryPath
// ---------------------------------------------------------------------------

describe('parseEntryPath', () => {
  it('parses plain file picks (no folder)', () => {
    expect(parseEntryPath(mkFile('a.txt'))).toEqual({ segments: [], filename: 'a.txt' });
  });

  it('preserves nested folder hierarchy from webkitRelativePath', () => {
    expect(parseEntryPath(mkFile('c.pdf', 'Top/Sub/Deep/c.pdf'))).toEqual({
      segments: ['Top', 'Sub', 'Deep'],
      filename: 'c.pdf',
    });
  });

  it('handles same filename in different folders', () => {
    const a = parseEntryPath(mkFile('readme.md', 'ProjectA/readme.md'));
    const b = parseEntryPath(mkFile('readme.md', 'ProjectB/readme.md'));
    expect(a.segments).toEqual(['ProjectA']);
    expect(b.segments).toEqual(['ProjectB']);
    expect(a.filename).toBe('readme.md');
    expect(b.filename).toBe('readme.md');
  });

  it('REJECTS path traversal in relative path', () => {
    expect(parseEntryPath(mkFile('evil.txt', '../evil.txt'))).toBeNull();
    expect(parseEntryPath(mkFile('evil.txt', 'a/../../evil.txt'))).toBeNull();
    expect(parseEntryPath(mkFile('..', ''))).toBeNull();
    expect(parseEntryPath(mkFile('x.txt', 'a/..//x.txt'))).toBeNull();
  });

  it('REJECTS traversal inside the filename itself', () => {
    expect(parseEntryPath(mkFile('..', 'Folder/..'))).toBeNull();
  });

  it('rejects empty/garbage input', () => {
    expect(parseEntryPath(null)).toBeNull();
    expect(parseEntryPath(mkFile(''))).toBeNull();
  });
});

// ---------------------------------------------------------------------------
// buildFolderCache + resolveFolderPath (reuse, never duplicate)
// ---------------------------------------------------------------------------

describe('buildFolderCache', () => {
  it('keys folders by parent + sanitized name', () => {
    const cache = buildFolderCache([
      { id: 'f-root', name: 'Top', parent_id: null },
      { id: 'f-sub', name: 'Sub', parent_id: 'f-root' },
    ]);
    expect(cache.get('root/Top')).toBe('f-root');
    expect(cache.get('f-root/Sub')).toBe('f-sub');
  });

  it('ignores malformed folders', () => {
    const cache = buildFolderCache([null, { name: 'x' }, { id: 'f', name: '..' }]);
    expect(cache.size).toBe(0);
  });
});

describe('resolveFolderPath', () => {
  it('creates missing levels and reuses cached ones', async () => {
    const cache = buildFolderCache([{ id: 'f-root', name: 'Top', parent_id: null }]);
    const api = { post: vi.fn(async (url, body) => ({ id: `new-${body.name}` })) };

    const result = await resolveFolderPath(api, ['Top', 'Sub', 'Deep'], cache);

    // Only Sub + Deep created; Top reused from cache.
    expect(api.post).toHaveBeenCalledTimes(2);
    expect(api.post).toHaveBeenNthCalledWith(1, '/folders', {
      name: 'Sub',
      parent_id: 'f-root',
    });
    expect(api.post).toHaveBeenNthCalledWith(2, '/folders', {
      name: 'Deep',
      parent_id: 'new-Sub',
    });
    expect(result).toBe('new-Deep');
  });

  it('returns null (root) for empty segments and makes no calls', async () => {
    const api = { post: vi.fn() };
    expect(await resolveFolderPath(api, [], new Map())).toBeNull();
    expect(api.post).not.toHaveBeenCalled();
  });

  it('reuses folders created earlier in the same batch (no duplicates)', async () => {
    const cache = new Map();
    const api = { post: vi.fn(async (url, body) => ({ id: `id-${body.name}` })) };

    await resolveFolderPath(api, ['A'], cache);
    await resolveFolderPath(api, ['A'], cache);

    expect(api.post).toHaveBeenCalledTimes(1);
  });
});

// ---------------------------------------------------------------------------
// uploadEntry
// ---------------------------------------------------------------------------

describe('uploadEntry', () => {
  it('ensures folders, creates doc, uploads bytes to the existing endpoint', async () => {
    const api = {
      post: vi.fn(async (url, body) => {
        if (url === '/documents') return { id: 'doc-1' };
        return { id: 'folder-x' };
      }),
    };
    const uploadFn = vi.fn(async () => ({ id: 'doc-1' }));
    const entry = entryFor('c.pdf', 'Top/c.pdf');

    const result = await uploadEntry({
      api,
      uploadFn,
      folderCache: new Map(),
      entry,
      onProgress: () => {},
    });

    expect(api.post).toHaveBeenCalledWith('/documents', {
      name: 'c.pdf',
      folder_id: 'folder-x',
    });
    expect(uploadFn).toHaveBeenCalledTimes(1);
    const [endpoint, formData] = uploadFn.mock.calls[0];
    expect(endpoint).toBe('/documents/doc-1/upload');
    expect(formData).toBeInstanceOf(FormData);
    expect(result.id).toBe('doc-1');
  });

  it('propagates upload failure (queue isolates it per-file)', async () => {
    const api = {
      post: vi.fn(async (url) => (url === '/documents' ? { id: 'doc-2' } : { id: null })),
    };
    const uploadFn = vi.fn(async () => {
      throw new Error('File size exceeds maximum allowed limit of 10 bytes.');
    });

    await expect(
      uploadEntry({
        api,
        uploadFn,
        folderCache: new Map(),
        entry: entryFor('big.bin'),
      })
    ).rejects.toThrow(/exceeds maximum/);
  });
});

// ---------------------------------------------------------------------------
// createUploadQueue
// ---------------------------------------------------------------------------

describe('createUploadQueue', () => {
  let api;
  let uploadFn;
  let uploads;

  beforeEach(() => {
    uploads = [];
    api = {
      post: vi.fn(async (url, body) => {
        if (url === '/documents') return { id: `doc-${body.name}` };
        return { id: `folder-${body.name}` };
      }),
    };
    uploadFn = vi.fn(async (endpoint) => {
      uploads.push(endpoint);
      return { id: 'ok' };
    });
  });

  it('uploads every entry exactly once and reports per-file state', async () => {
    const entries = [
      entryFor('a.txt', 'F1/a.txt'),
      entryFor('b.txt', 'F1/F2/b.txt'),
      entryFor('c.txt'),
    ];
    const states = [];
    const queue = createUploadQueue({
      entries,
      api,
      uploadFn,
      concurrency: 2,
      onStateChange: (s) => states.push(s),
    });

    await queue.run();
    const snap = queue.snapshot();

    expect(snap).toHaveLength(3);
    expect(snap.every((i) => i.status === 'done')).toBe(true);
    expect(snap.every((i) => i.progress === 100)).toBe(true);
    expect(uploads).toHaveLength(3);
    // Final state snapshot was emitted.
    expect(states.length).toBeGreaterThan(0);
  });

  it('same filename in different folders → separate documents, no collision', async () => {
    const queue = createUploadQueue({
      entries: [entryFor('readme.md', 'PA/readme.md'), entryFor('readme.md', 'PB/readme.md')],
      api,
      uploadFn,
      concurrency: 1,
    });
    await queue.run();
    const snap = queue.snapshot();
    expect(snap.every((i) => i.status === 'done')).toBe(true);
    const docCalls = api.post.mock.calls.filter(([url]) => url === '/documents');
    expect(docCalls).toHaveLength(2);
    // Distinct folder chains → distinct folder_ids.
    expect(docCalls[0][1].folder_id).not.toBe(docCalls[1][1].folder_id);
    expect(docCalls[0][1].name).toBe('readme.md');
  });

  it('isolates per-file failures and retryFailed re-runs ONLY failed files', async () => {
    const entries = [entryFor('ok1.txt'), entryFor('bad.txt'), entryFor('ok2.txt')];
    let failOnce = true;
    uploadFn = vi.fn(async (endpoint) => {
      uploads.push(endpoint);
      if (endpoint.includes('doc-bad.txt') && failOnce) {
        failOnce = false;
        throw new Error('Network error. Please check your internet connection.');
      }
      return { id: 'ok' };
    });

    const queue = createUploadQueue({ entries, api, uploadFn, concurrency: 1 });
    await queue.run();

    let snap = queue.snapshot();
    expect(snap.find((i) => i.entry.filename === 'bad.txt').status).toBe('error');
    expect(snap.find((i) => i.entry.filename === 'bad.txt').error).toMatch(/Network error/);
    expect(snap.filter((i) => i.status === 'done')).toHaveLength(2);

    // Retry: only the failed file is re-uploaded (successful ones untouched).
    const uploadsBefore = uploads.length;
    await queue.retryFailed();
    snap = queue.snapshot();

    expect(snap.every((i) => i.status === 'done')).toBe(true);
    expect(uploads.length - uploadsBefore).toBe(1);
    expect(uploads[uploads.length - 1]).toContain('doc-bad.txt');
  });

  it('empty queue resolves cleanly', async () => {
    const queue = createUploadQueue({ entries: [], api, uploadFn });
    await queue.run();
    expect(queue.snapshot()).toEqual([]);
    expect(uploadFn).not.toHaveBeenCalled();
  });

  it('cancel() stops remaining items', async () => {
    const entries = Array.from({ length: 6 }, (_, i) => entryFor(`f${i}.txt`));
    uploadFn = vi.fn(async (endpoint) => {
      uploads.push(endpoint);
      return { id: 'ok' };
    });
    const queue = createUploadQueue({
      entries,
      api,
      uploadFn,
      concurrency: 1,
      onStateChange: (snap) => {
        const done = snap.filter((i) => i.status === 'done').length;
        if (done === 2) queue.cancel();
      },
    });
    await queue.run();
    const snap = queue.snapshot();
    expect(snap.filter((i) => i.status === 'done').length).toBeLessThan(6);
    expect(snap.some((i) => i.status === 'pending')).toBe(true);
  });
});
