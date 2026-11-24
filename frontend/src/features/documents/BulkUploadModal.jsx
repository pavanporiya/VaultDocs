import React, { useRef, useState } from 'react';
import { Modal, Button, useToast } from '../../shared/components';
import apiClient, { uploadWithProgress } from '../../shared/services/apiClient';
import { FolderOpen, FilePlus2, Upload, RotateCcw, X } from 'lucide-react';
import { formatFileSize } from '../../shared/utils/format';
import {
  buildFolderCache,
  createUploadQueue,
  parseEntryPath,
} from './bulkUpload';

/**
 * Bulk Upload modal — multiple files AND full-folder upload.
 *
 * Reuses the existing backend architecture (no new endpoints):
 * - GET/POST /folders        → reuse or create the nested folder hierarchy
 * - POST /documents          → one new document record per file
 * - POST /documents/{id}/upload → file bytes (existing auth/size validation)
 *
 * Every file gets its OWN new document record, so an existing document with
 * the same name is never overwritten. Failed files can be retried without
 * re-uploading successful ones.
 *
 * Props:
 * - isOpen: modal visibility
 * - onClose: called when the modal closes (blocked while uploading)
 * - onDone: called after a run/retry finishes (caller refreshes lists)
 */
export const BulkUploadModal = ({ isOpen, onClose, onDone }) => {
  const [entries, setEntries] = useState([]); // {file, segments, filename, size}
  const [rejected, setRejected] = useState([]); // raw names that failed sanitization
  const [items, setItems] = useState([]); // queue snapshots
  const [running, setRunning] = useState(false);
  const [started, setStarted] = useState(false);
  const queueRef = useRef(null);
  const filesInputRef = useRef(null);
  const folderInputRef = useRef(null);
  const toast = useToast();

  const addFiles = (fileList) => {
    const next = [];
    const bad = [];
    Array.from(fileList || []).forEach((file) => {
      const parsed = parseEntryPath(file);
      if (parsed) {
        next.push({ file, ...parsed, size: file.size });
      } else {
        bad.push(file.name || '(unnamed)');
      }
    });
    if (next.length > 0) {
      setEntries((prev) => {
        // De-dupe identical (relative path + size) picks to avoid double submits.
        const seen = new Set(prev.map((e) => `${e.segments.join('/')}/${e.filename}:${e.size}`));
        return [
          ...prev,
          ...next.filter((e) => {
            const key = `${e.segments.join('/')}/${e.filename}:${e.size}`;
            if (seen.has(key)) return false;
            seen.add(key);
            return true;
          }),
        ];
      });
    }
    setRejected(bad);
  };

  const removeEntry = (index) => {
    setEntries((prev) => prev.filter((_, i) => i !== index));
  };

  const handleStart = async () => {
    if (entries.length === 0 || running) return;
    setRunning(true);
    setStarted(true);
    try {
      // Seed the folder cache with the user's existing folders so matching
      // paths are REUSED instead of duplicated.
      const existingFolders = await apiClient.get('/folders');
      const queue = createUploadQueue({
        entries,
        api: apiClient,
        uploadFn: uploadWithProgress,
        concurrency: 3,
        onStateChange: setItems,
        initialFolderCache: buildFolderCache(existingFolders),
      });
      queueRef.current = queue;
      await queue.run();
      const snap = queue.snapshot();
      const done = snap.filter((i) => i.status === 'done').length;
      const failed = snap.filter((i) => i.status === 'error').length;
      if (failed === 0) {
        toast.success(`${done} file${done === 1 ? '' : 's'} uploaded successfully.`);
      } else {
        toast.error(
          `${done} uploaded, ${failed} failed. Use "Retry Failed" to retry.`,
          'Bulk upload finished with errors'
        );
      }
      if (typeof onDone === 'function') onDone();
    } catch (err) {
      toast.error(err.message || 'Bulk upload failed.', 'Upload Error');
    } finally {
      setRunning(false);
    }
  };

  const handleRetryFailed = async () => {
    // Reuse the SAME queue (and its seeded folder cache): retryFailed() re-runs
    // only error items; done items are never re-uploaded.
    if (running || !queueRef.current) return;
    setRunning(true);
    try {
      await queueRef.current.retryFailed();
      const snap = queueRef.current.snapshot();
      const failed = snap.filter((i) => i.status === 'error').length;
      if (failed === 0) {
        toast.success('All retried files uploaded successfully.');
      } else {
        toast.error(`${failed} file(s) still failing.`, 'Retry finished with errors');
      }
      if (typeof onDone === 'function') onDone();
    } catch (err) {
      toast.error(err.message || 'Retry failed.', 'Upload Error');
    } finally {
      setRunning(false);
    }
  };

  const handleClose = () => {
    if (running) {
      toast.error('Upload in progress — please wait or cancel first.', 'Busy');
      return;
    }
    setEntries([]);
    setItems([]);
    setRejected([]);
    setStarted(false);
    queueRef.current = null;
    onClose();
  };

  const failedCount = items.filter((i) => i.status === 'error').length;
  const doneCount = items.filter((i) => i.status === 'done').length;
  const showQueue = items.length > 0;

  const displayPath = (e) =>
    e.segments.length > 0 ? `${e.segments.join('/')}/${e.filename}` : e.filename;

  return (
    <Modal isOpen={isOpen} onClose={handleClose} title="Bulk Upload (Files & Folders)" size="md">
      <div className="vd-form vd-bulk-upload">
        <p className="vd-bulk-note">
          Select multiple files or a complete folder (nested subfolders are preserved). Each file
          becomes its own document — existing documents are never overwritten. Empty subfolders
          cannot be detected by the browser and are skipped.
        </p>

        <div className="vd-bulk-actions">
          <input
            ref={filesInputRef}
            type="file"
            multiple
            style={{ display: 'none' }}
            onChange={(e) => {
              addFiles(e.target.files);
              e.target.value = '';
            }}
            disabled={running}
          />
          <input
            ref={folderInputRef}
            type="file"
            webkitdirectory=""
            directory=""
            multiple
            style={{ display: 'none' }}
            onChange={(e) => {
              addFiles(e.target.files);
              e.target.value = '';
            }}
            disabled={running}
          />
          <Button
            type="button"
            variant="secondary"
            icon={FilePlus2}
            onClick={() => filesInputRef.current?.click()}
            disabled={running || started}
          >
            Add Files
          </Button>
          <Button
            type="button"
            variant="secondary"
            icon={FolderOpen}
            onClick={() => folderInputRef.current?.click()}
            disabled={running || started}
          >
            Add Folder
          </Button>
        </div>

        {rejected.length > 0 && (
          <span className="vd-bulk-rejected">
            Skipped unsafe/invalid entries: {rejected.join(', ')}
          </span>
        )}

        {!showQueue && (
          <ul className="vd-bulk-list" aria-label="Selected files">
            {entries.map((e, i) => (
              <li key={`${displayPath(e)}:${e.size}:${i}`} className="vd-bulk-item">
                <span className="vd-bulk-item-name" title={displayPath(e)}>
                  {displayPath(e)}
                </span>
                <span className="vd-bulk-item-size">({formatFileSize(e.size)})</span>
                <button
                  type="button"
                  className="vd-bulk-item-remove"
                  title="Remove from selection"
                  onClick={() => removeEntry(i)}
                  disabled={running}
                >
                  <X size={14} />
                </button>
              </li>
            ))}
            {entries.length === 0 && <li className="vd-bulk-empty">No files selected yet.</li>}
          </ul>
        )}

        {showQueue && (
          <ul className="vd-bulk-list vd-bulk-queue" aria-label="Upload queue">
            {items.map((item) => {
              const path = displayPath(item.entry);
              return (
                <li key={path} className="vd-bulk-item">
                  <span className="vd-bulk-item-name" title={path}>
                    {path}
                  </span>
                  <span className="vd-bulk-item-size">{formatFileSize(item.entry.size)}</span>
                  {item.status === 'uploading' && (
                    <span className="vd-bulk-progress" aria-label={`Uploading ${path}`}>
                      <progress value={item.progress} max={100} />
                      {item.progress}%
                    </span>
                  )}
                  <span className={`vd-bulk-status vd-bulk-status-${item.status}`}>
                    {item.status === 'pending' && 'Pending'}
                    {item.status === 'uploading' && 'Uploading…'}
                    {item.status === 'done' && 'Done'}
                    {item.status === 'error' && `Failed${item.error ? `: ${item.error}` : ''}`}
                  </span>
                </li>
              );
            })}
          </ul>
        )}

        <div className="vd-modal-footer">
          <Button variant="secondary" type="button" onClick={handleClose} disabled={running}>
            {running ? 'Uploading…' : 'Close'}
          </Button>
          {showQueue && failedCount > 0 && !running && (
            <Button variant="secondary" type="button" icon={RotateCcw} onClick={handleRetryFailed}>
              Retry Failed ({failedCount})
            </Button>
          )}
          {!showQueue ? (
            <Button
              variant="primary"
              type="button"
              icon={Upload}
              onClick={handleStart}
              disabled={entries.length === 0 || running}
            >
              Upload{' '}
              {entries.length > 0 ? `${entries.length} File${entries.length === 1 ? '' : 's'}` : ''}
            </Button>
          ) : (
            <Button
              variant="primary"
              type="button"
              onClick={handleClose}
              disabled={running || doneCount + failedCount < items.length}
            >
              {doneCount}/{items.length} Uploaded
            </Button>
          )}
        </div>
      </div>
    </Modal>
  );
};

export default BulkUploadModal;
