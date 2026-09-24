import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  PageHeader,
  Card,
  Button,
  Input,
  Select,
  Modal,
  Loader,
  ErrorState,
  useToast,
} from '../../shared/components';
import apiClient, { downloadFile, saveBlob } from '../../shared/services/apiClient';
import { useAuth } from '../../shared/context/AuthContext';
import VersionsModal from './VersionsModal';
import SharesModal from './SharesModal';
import UploadModal from './UploadModal';
import { formatFileSize, formatDate, hasStoredFile } from '../../shared/utils/format';
import { getPreviewKind, MAX_TEXT_PREVIEW_BYTES } from '../../shared/utils/fileTypes';
import {
  FileText,
  Download,
  Upload,
  History,
  Share2,
  Trash2,
  Edit2,
  FolderInput,
  RefreshCw,
  ArrowLeft,
  Eye,
  FileWarning,
  Lock,
} from 'lucide-react';
import './DocumentDetailView.css';

/**
 * Client-side fallback flags for older API responses without the
 * authorization fields (owner-shaped defaults preserve owner flows).
 */
const resolvePermissions = (doc) => ({
  isOwner: doc?.is_owner !== false,
  canEdit: doc?.can_edit !== false,
  canDownload: doc?.can_download !== false,
  canShare: doc?.can_share !== false,
  canDelete: doc?.can_delete !== false,
});

/**
 * Document Details — the central workspace for a single document.
 *
 * Data comes exclusively from the real backend:
 * - GET  /documents/{id}                     document metadata
 * - GET  /documents/{id}/versions            version count + history modal
 * - GET  /documents/{id}/download            preview + download
 * - GET  /folders                            folder picker for moving
 * - PATCH /documents/{id}                    rename / move
 * - POST|PUT /documents/{id}/upload          upload / replace (UploadModal)
 * - DELETE /documents/{id}                   delete
 */
export const DocumentDetailView = ({ documentId, onNavigate }) => {
  const { isAuthenticated, isLoading: authLoading } = useAuth();
  const toast = useToast();

  const [document, setDocument] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [notFound, setNotFound] = useState(false);

  const [folders, setFolders] = useState([]);
  const [versionCount, setVersionCount] = useState(null);

  // Modal state
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [uploadMode, setUploadMode] = useState('POST');
  const [isVersionsModalOpen, setIsVersionsModalOpen] = useState(false);
  const [isSharesModalOpen, setIsSharesModalOpen] = useState(false);
  const [isRenameModalOpen, setIsRenameModalOpen] = useState(false);
  const [isMoveModalOpen, setIsMoveModalOpen] = useState(false);
  const [isDeleteModalOpen, setIsDeleteModalOpen] = useState(false);

  // Form state
  const [renameValue, setRenameValue] = useState('');
  const [moveFolderId, setMoveFolderId] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [downloading, setDownloading] = useState(false);

  // Preview state
  const [previewState, setPreviewState] = useState('idle'); // idle|loading|ready|error
  const [previewError, setPreviewError] = useState('');
  const [textContent, setTextContent] = useState('');
  const previewUrlRef = useRef(null);
  const previewTokenRef = useRef(0);

  const clearPreviewUrl = () => {
    if (previewUrlRef.current) {
      window.URL.revokeObjectURL(previewUrlRef.current);
      previewUrlRef.current = null;
    }
  };

  const fetchDocument = useCallback(async () => {
    if (!documentId) return;
    setLoading(true);
    setError('');
    setNotFound(false);
    try {
      const doc = await apiClient.get(`/documents/${documentId}`);
      setDocument(doc);
    } catch (err) {
      if (err?.status === 404) {
        setNotFound(true);
      } else {
        setError(err.message || 'Failed to load document.');
      }
    } finally {
      setLoading(false);
    }
  }, [documentId]);

  // Version count is real backend data used for the history shortcut.
  const fetchVersionCount = useCallback(async () => {
    if (!documentId) return;
    try {
      const versions = await apiClient.get(`/documents/${documentId}/versions`);
      setVersionCount(Array.isArray(versions) ? versions.length : null);
    } catch {
      setVersionCount(null);
    }
  }, [documentId]);

  const fetchFolders = useCallback(async () => {
    try {
      const data = await apiClient.get('/folders');
      setFolders(data || []);
    } catch {
      setFolders([]);
    }
  }, []);

  useEffect(() => {
    if (!isAuthenticated || authLoading) return;
    fetchDocument();
    fetchVersionCount();
    fetchFolders();
  }, [isAuthenticated, authLoading, fetchDocument, fetchVersionCount, fetchFolders]);

  // ------------------------------------------------------------------
  // Preview loading (authenticated, blob-based; no storage paths exposed)
  // ------------------------------------------------------------------
  useEffect(() => {
    if (!document) return;
    const kind = getPreviewKind(document.content_type, document.original_filename);
    if (!kind || !hasStoredFile(document)) {
      setPreviewState('idle');
      return;
    }

    const token = ++previewTokenRef.current;
    setPreviewState('loading');
    setPreviewError('');
    setTextContent('');

    (async () => {
      try {
        // Dedicated inline preview stream: readable by the owner AND
        // view-only ("seen") recipients. The attachment /download endpoint
        // 403s for view-only shares, so preview must not use it.
        const { blob } = await downloadFile(`/documents/${document.id}/preview`);

        // A newer load started meanwhile — discard this result.
        if (previewTokenRef.current !== token) return;

        if (kind === 'text') {
          if (blob.size > MAX_TEXT_PREVIEW_BYTES) {
            setPreviewState('error');
            setPreviewError(
              `Text file is too large to preview (${formatFileSize(blob.size)}). Download it instead.`
            );
            return;
          }
          const text = await blob.text();
          if (previewTokenRef.current !== token) return;
          setTextContent(text);
          setPreviewState('ready');
        } else {
          clearPreviewUrl();
          previewUrlRef.current = window.URL.createObjectURL(blob);
          if (previewTokenRef.current !== token) return;
          setPreviewState('ready');
        }
      } catch (err) {
        if (previewTokenRef.current !== token) return;
        setPreviewState('error');
        setPreviewError(err.message || 'Preview could not be loaded.');
      }
    })();

    return clearPreviewUrl;
  }, [document]);

  // ------------------------------------------------------------------
  // Actions
  // ------------------------------------------------------------------
  const handleDownload = async () => {
    if (!document) return;
    setDownloading(true);
    try {
      const { blob, filename } = await downloadFile(`/documents/${document.id}/download`);
      saveBlob(blob, filename || document.original_filename || document.name);
      toast.success(`Downloaded "${filename || document.name}"`);
    } catch (err) {
      const message =
        err?.status === 404
          ? 'No file has been uploaded for this document yet.'
          : err.message || 'Download failed.';
      toast.error(message, 'Download Error');
    } finally {
      setDownloading(false);
    }
  };

  const handleRename = async (e) => {
    e.preventDefault();
    if (!renameValue.trim() || !document) return;
    setSubmitting(true);
    try {
      const updated = await apiClient.patch(`/documents/${document.id}`, {
        name: renameValue.trim(),
      });
      setDocument(updated);
      toast.success('Document renamed.');
      setIsRenameModalOpen(false);
    } catch (err) {
      toast.error(err.message || 'Rename failed.', 'Error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleMove = async (e) => {
    e.preventDefault();
    if (!document) return;
    setSubmitting(true);
    try {
      const updated = await apiClient.patch(`/documents/${document.id}`, {
        folder_id: moveFolderId || null,
      });
      setDocument(updated);
      toast.success('Document moved.');
      setIsMoveModalOpen(false);
    } catch (err) {
      toast.error(err.message || 'Move failed.', 'Error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async () => {
    if (!document) return;
    setSubmitting(true);
    try {
      await apiClient.delete(`/documents/${document.id}`);
      toast.success(`Document "${document.name}" deleted.`);
      setIsDeleteModalOpen(false);
      if (onNavigate) onNavigate('/documents');
    } catch (err) {
      toast.error(err.message || 'Delete failed.', 'Error');
      setSubmitting(false);
      setIsDeleteModalOpen(false);
    }
  };

  const handleUploaded = (updatedDoc) => {
    if (updatedDoc) {
      setDocument(updatedDoc);
    } else {
      fetchDocument();
    }
    fetchVersionCount();
  };

  const openRename = () => {
    setRenameValue(document?.name || '');
    setIsRenameModalOpen(true);
  };

  const openMove = () => {
    setMoveFolderId(document?.folder_id || '');
    setIsMoveModalOpen(true);
  };

  // ------------------------------------------------------------------
  // Authorization flags (server-authoritative, with legacy fallback)
  // ------------------------------------------------------------------
  const perms = resolvePermissions(document);
  const isOwner = perms.isOwner;
  const canEdit = perms.canEdit;
  const canDownload = perms.canDownload;

  const openSharesModal = () => {
    if (!isOwner) return;
    setIsSharesModalOpen(true);
  };

  // ------------------------------------------------------------------
  // Render helpers
  // ------------------------------------------------------------------
  const folderName = document?.folder_id
    ? folders.find((f) => f.id === document.folder_id)?.name || 'Folder'
    : 'Root (No Folder)';

  const folderOptions = [
    { value: '', label: 'Root (No Folder)' },
    ...folders
      .filter((f) => f.id !== document?.folder_id)
      .map((f) => ({ value: f.id, label: f.name })),
  ];

  const renderPreview = () => {
    if (!document) return null;

    if (!hasStoredFile(document)) {
      return (
        <div className="vd-docdetail-preview-empty">
          <FileWarning size={32} />
          <span>No file uploaded yet. Use "Upload / Replace File" to add one.</span>
        </div>
      );
    }

    const kind = getPreviewKind(document.content_type, document.original_filename);

    if (!kind) {
      return (
        <div className="vd-docdetail-preview-unavailable">
          <FileWarning size={32} />
          <span>
            Preview unavailable for this file type
            {document.content_type ? ` (${document.content_type})` : ''}.
          </span>
          {canDownload && (
            <Button variant="outline" size="sm" icon={Download} onClick={handleDownload}>
              Download Instead
            </Button>
          )}
        </div>
      );
    }

    if (previewState === 'loading') {
      return (
        <div style={{ padding: '2rem 0', textAlign: 'center' }}>
          <Loader text="Loading preview..." />
        </div>
      );
    }

    // Loading an authenticated blob is async, so the object URL can briefly
    // be absent on the very first render after 'ready'. Show a loader
    // instead of an empty frame until it is set (text previews render from
    // state instead and are unaffected).
    if ((kind === 'pdf' || kind === 'image') && !previewUrlRef.current) {
      return (
        <div style={{ padding: '2rem 0', textAlign: 'center' }}>
          <Loader text="Preparing preview..." />
        </div>
      );
    }

    if (previewState === 'error') {
      return (
        <div className="vd-docdetail-preview-unavailable">
          <FileWarning size={32} />
          <span>{previewError || 'Preview unavailable.'}</span>
          {canDownload && (
            <Button variant="outline" size="sm" icon={Download} onClick={handleDownload}>
              Download Instead
            </Button>
          )}
        </div>
      );
    }

    if (previewState !== 'ready') return null;

    if (kind === 'pdf') {
      return (
        <iframe
          title={`Preview of ${document.name}`}
          className="vd-docdetail-preview-frame"
          src={previewUrlRef.current || undefined}
        />
      );
    }

    if (kind === 'image') {
      return (
        <div className="vd-docdetail-preview-image-wrap">
          <img
            className="vd-docdetail-preview-image"
            src={previewUrlRef.current || undefined}
            alt={`Preview of ${document.name}`}
          />
        </div>
      );
    }

    return (
      <pre className="vd-docdetail-preview-text">{textContent}</pre>
    );
  };

  // ------------------------------------------------------------------
  // Guard states
  // ------------------------------------------------------------------
  if (!isAuthenticated && !authLoading) {
    return (
      <div className="vd-docdetail">
        <PageHeader title="Document Details" description="Single document workspace." />
        <Card elevation="sm" style={{ padding: '3rem', textAlign: 'center' }}>
          <h3>Authentication Required</h3>
          <p style={{ color: 'var(--color-text-muted)', margin: '1rem 0' }}>
            Please log in to view this document.
          </p>
          <Button variant="primary" onClick={() => onNavigate && onNavigate('/login')}>
            Sign In
          </Button>
        </Card>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="vd-docdetail">
        <div style={{ padding: '3rem 0', textAlign: 'center' }}>
          <Loader text="Loading document..." />
        </div>
      </div>
    );
  }

  if (notFound) {
    return (
      <div className="vd-docdetail">
        <PageHeader title="Document Details" />
        <ErrorState
          title="Document not found"
          description="This document does not exist, was deleted, or is not shared with you."
        />
        <div className="vd-docdetail-backrow">
          <Button variant="outline" icon={ArrowLeft} onClick={() => onNavigate && onNavigate('/documents')}>
            Back to All Documents
          </Button>
        </div>
      </div>
    );
  }

  if (error || !document) {
    return (
      <div className="vd-docdetail">
        <PageHeader title="Document Details" />
        <ErrorState
          title="Could not load document"
          description={error || 'An unexpected error occurred.'}
          onRetry={fetchDocument}
        />
      </div>
    );
  }

  return (
    <div className="vd-docdetail">
      <PageHeader
        breadcrumbs={[
          { label: 'Dashboard', onClick: () => onNavigate && onNavigate('/dashboard') },
          { label: 'All Documents', onClick: () => onNavigate && onNavigate('/documents') },
          { label: document.name },
        ]}
        title={document.name}
        description={
          hasStoredFile(document)
            ? `${document.original_filename || 'Stored file'} · ${formatFileSize(document.file_size)}`
            : 'No file uploaded yet.'
        }
        actions={
          <div className="vd-docdetail-actions">
            {canDownload ? (
              <Button
                variant="outline"
                icon={Download}
                loading={downloading}
                onClick={handleDownload}
                disabled={!hasStoredFile(document)}
              >
                Download
              </Button>
            ) : (
              <Button
                variant="outline"
                icon={Download}
                disabled
                title="Download disabled: View-only access"
                aria-label="Download disabled: View-only access"
              >
                Download
              </Button>
            )}
            {canEdit && (
              <Button
                variant="primary"
                icon={Upload}
                onClick={() => {
                  setUploadMode(hasStoredFile(document) ? 'PUT' : 'POST');
                  setIsUploadModalOpen(true);
                }}
              >
                {hasStoredFile(document) ? 'Upload / Replace' : 'Upload File'}
              </Button>
            )}
          </div>
        }
      />

      <div className="vd-docdetail-grid">
        {/* Metadata */}
        <Card title="Document Information" elevation="sm">
          {!isOwner && (
            <div className="vd-docdetail-readonly-banner" role="status">
              <Lock size={16} />
              <span>You have read-only access to this document.</span>
            </div>
          )}
          <div className="vd-docdetail-info-list">
            <div className="vd-docdetail-info-row">
              <span className="vd-docdetail-info-label">Access</span>
              <span className="vd-docdetail-info-value">
                {isOwner ? (
                  <span className="vd-badge vd-badge-owner">Owner</span>
                ) : canDownload ? (
                  <span className="vd-badge vd-badge-readonly">View + Download</span>
                ) : (
                  <span className="vd-badge vd-badge-readonly">View Only Access</span>
                )}
              </span>
            </div>
            <div className="vd-docdetail-info-row">
              <span className="vd-docdetail-info-label">Name</span>
              <span className="vd-docdetail-info-value">
                <FileText size={16} className="vd-docdetail-name-icon" />
                {document.name}
              </span>
            </div>
            <div className="vd-docdetail-info-row">
              <span className="vd-docdetail-info-label">Original File</span>
              <span className="vd-docdetail-info-value">
                {document.original_filename || 'No file uploaded'}
              </span>
            </div>
            <div className="vd-docdetail-info-row">
              <span className="vd-docdetail-info-label">Size</span>
              <span className="vd-docdetail-info-value">{formatFileSize(document.file_size)}</span>
            </div>
            <div className="vd-docdetail-info-row">
              <span className="vd-docdetail-info-label">Content Type</span>
              <span className="vd-docdetail-info-value">{document.content_type || '—'}</span>
            </div>
            <div className="vd-docdetail-info-row">
              <span className="vd-docdetail-info-label">Folder</span>
              <span className="vd-docdetail-info-value">{folderName}</span>
            </div>
            <div className="vd-docdetail-info-row">
              <span className="vd-docdetail-info-label">Versions</span>
              <span className="vd-docdetail-info-value">
                {versionCount === null ? '—' : `${versionCount} recorded`}
              </span>
            </div>
            <div className="vd-docdetail-info-row">
              <span className="vd-docdetail-info-label">Created</span>
              <span className="vd-docdetail-info-value">{formatDate(document.created_at, { withTime: true })}</span>
            </div>
            <div className="vd-docdetail-info-row">
              <span className="vd-docdetail-info-label">Updated</span>
              <span className="vd-docdetail-info-value">{formatDate(document.updated_at, { withTime: true })}</span>
            </div>
          </div>

          <div className="vd-docdetail-manage">
            <h4 className="vd-docdetail-manage-title">Manage</h4>
            <div className="vd-docdetail-manage-actions">
              {isOwner && (
                <>
                  <Button variant="ghost" size="sm" icon={Edit2} onClick={openRename}>
                    Rename
                  </Button>
                  <Button variant="ghost" size="sm" icon={FolderInput} onClick={openMove}>
                    Move
                  </Button>
                </>
              )}
              <Button
                variant="ghost"
                size="sm"
                icon={History}
                onClick={() => setIsVersionsModalOpen(true)}
              >
                Version History{versionCount !== null ? ` (${versionCount})` : ''}
              </Button>
              {isOwner && (
                <>
                  <Button variant="ghost" size="sm" icon={Share2} onClick={openSharesModal}>
                    Share
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    icon={RefreshCw}
                    onClick={fetchDocument}
                  >
                    Refresh
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="vd-docdetail-danger"
                    icon={Trash2}
                    onClick={() => setIsDeleteModalOpen(true)}
                  >
                    Delete
                  </Button>
                </>
              )}
            </div>
          </div>
        </Card>

        {/* Preview */}
        <Card
          title="Preview"
          subtitle="Safe in-browser preview for supported formats"
          elevation="sm"
          headerAction={
            canDownload && (
              <Button
                variant="ghost"
                size="sm"
                icon={Eye}
                disabled={!hasStoredFile(document)}
                onClick={handleDownload}
              >
                Download
              </Button>
            )
          }
        >
          <div className="vd-docdetail-preview">{renderPreview()}</div>
        </Card>
      </div>

      {/* Upload / Replace (owners only) */}
      {canEdit && (
        <UploadModal
          isOpen={isUploadModalOpen}
          document={document}
          mode={uploadMode}
          onClose={() => setIsUploadModalOpen(false)}
          onUploaded={handleUploaded}
        />
      )}

      {/* Version history (enhanced modal with version details) */}
      <VersionsModal
        isOpen={isVersionsModalOpen}
        onClose={() => setIsVersionsModalOpen(false)}
        document={document}
      />

      {/* Sharing (owner only) */}
      {isOwner && (
        <SharesModal
          isOpen={isSharesModalOpen}
          onClose={() => setIsSharesModalOpen(false)}
          document={document}
        />
      )}

      {/* Rename */}
      <Modal
        isOpen={isRenameModalOpen}
        onClose={() => setIsRenameModalOpen(false)}
        title="Rename Document"
        size="sm"
      >
        <form onSubmit={handleRename} className="vd-docdetail-form">
          <Input
            label="Document Name"
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            required
            autoFocus
          />
          <div className="vd-modal-footer">
            <Button variant="secondary" type="button" onClick={() => setIsRenameModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" type="submit" loading={submitting}>
              Save
            </Button>
          </div>
        </form>
      </Modal>

      {/* Move */}
      <Modal
        isOpen={isMoveModalOpen}
        onClose={() => setIsMoveModalOpen(false)}
        title="Move Document"
        size="sm"
      >
        <form onSubmit={handleMove} className="vd-docdetail-form">
          <Select
            label="Target Folder"
            value={moveFolderId}
            onChange={(e) => setMoveFolderId(e.target.value)}
            options={folderOptions}
          />
          <div className="vd-modal-footer">
            <Button variant="secondary" type="button" onClick={() => setIsMoveModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="primary" type="submit" loading={submitting}>
              Move
            </Button>
          </div>
        </form>
      </Modal>

      {/* Delete confirm */}
      <Modal
        isOpen={isDeleteModalOpen}
        onClose={() => setIsDeleteModalOpen(false)}
        title="Delete Document"
        size="sm"
      >
        <p className="vd-docdetail-delete-text">
          Are you sure you want to delete <strong>{document.name}</strong>? This permanently removes
          the document, its file, version history, and all shares.
        </p>
        <div className="vd-modal-footer">
          <Button variant="secondary" onClick={() => setIsDeleteModalOpen(false)}>
            Cancel
          </Button>
          <Button variant="danger" loading={submitting} onClick={handleDelete}>
            Delete Permanently
          </Button>
        </div>
      </Modal>
    </div>
  );
};

export default DocumentDetailView;
