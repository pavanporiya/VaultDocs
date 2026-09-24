import React, { useState, useEffect, useCallback } from 'react';
import {
  PageHeader,
  Card,
  Table,
  Button,
  Input,
  Loader,
  ErrorState,
  useToast,
} from '../../shared/components';
import { useAuth } from '../../shared/context/AuthContext';
import apiClient, { downloadFile, saveBlob } from '../../shared/services/apiClient';
import { formatFileSize, formatDate, hasStoredFile, getDocumentDisplayName } from '../../shared/utils/format';
import { Download, ShieldCheck, Search, FileText, Lock, RefreshCw } from 'lucide-react';
import './SharedView.css';

/**
 * Shared With Me.
 *
 * Lists documents shared with the authenticated user via the real backend
 * endpoint GET /v1/documents/shared (name, owner, size, shared date).
 *
 * The manual UUID lookup is kept as a fallback: opening a document by ID
 * (GET /v1/documents/{id} — server-side access controlled) adds it to the
 * session list below the server results.
 */
export const SharedView = ({ onOpenAuthModal, onNavigate }) => {
  const { isAuthenticated } = useAuth();
  const [serverShared, setServerShared] = useState([]);
  const [manualDocs, setManualDocs] = useState([]);
  const [docIdInput, setDocIdInput] = useState('');

  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState('');
  const [lookupLoading, setLookupLoading] = useState(false);
  const [downloadingId, setDownloadingId] = useState(null);

  const toast = useToast();

  const fetchSharedList = useCallback(async () => {
    if (!isAuthenticated) return;
    setListLoading(true);
    setListError('');
    try {
      const data = await apiClient.get('/documents/shared');
      setServerShared(data || []);
    } catch (err) {
      setListError(err.message || 'Failed to load shared documents.');
    } finally {
      setListLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    fetchSharedList();
  }, [fetchSharedList]);

  const handleFetchSharedDoc = async (e) => {
    e.preventDefault();
    if (!docIdInput.trim()) return;

    setLookupLoading(true);
    try {
      const docData = await apiClient.get(`/documents/${docIdInput.trim()}`);
      setManualDocs((prev) => {
        const exists = prev.some((d) => d.id === docData.id);
        return exists ? prev : [docData, ...prev];
      });
      setDocIdInput('');
      toast.success(`Accessed shared document "${docData.name}"`);
    } catch (err) {
      const message =
        err?.status === 404
          ? 'Document not found — the ID is invalid, the document was deleted, or it is not shared with your account.'
          : err.message || 'Shared document lookup failed.';
      toast.error(message, 'Shared Access');
    } finally {
      setLookupLoading(false);
    }
  };

  const handleDownloadSharedFile = async (doc) => {
    setDownloadingId(doc.id);
    try {
      const { blob, filename } = await downloadFile(`/documents/${doc.id}/download`);
      saveBlob(blob, filename || getDocumentDisplayName(doc));
      toast.success(`Downloaded "${filename || doc.name}"`);
    } catch (err) {
      toast.error(err.message || 'Download failed.', 'Error');
    } finally {
      setDownloadingId(null);
    }
  };

  const openDocumentDetail = (doc) => {
    if (onNavigate) onNavigate(`/documents/${doc.id}`);
  };

  // Server results first; manually opened docs merged in (deduped by id).
  const serverIds = new Set(serverShared.map((d) => d.id));
  const mergedDocs = [
    ...manualDocs.filter((d) => !serverIds.has(d.id)),
    ...serverShared,
  ];

  const columns = [
    {
      header: 'Document Name',
      key: 'name',
      render: (row) => (
        <button
          type="button"
          className="vd-shared-doc-cell vd-shared-doc-link"
          onClick={() => openDocumentDetail(row)}
          title="Open document details"
        >
          <FileText size={18} className="vd-shared-doc-icon" />
          <span className="vd-shared-doc-name">{row.name}</span>
        </button>
      ),
    },
    {
      header: 'Shared By',
      key: 'shared_by_email',
      render: (row) =>
        row.shared_by_name || row.shared_by_email ? (
          <div className="vd-shared-owner">
            <span className="vd-shared-owner-name">{row.shared_by_name || 'Unknown owner'}</span>
            {row.shared_by_email && (
              <span className="vd-shared-owner-email">{row.shared_by_email}</span>
            )}
          </div>
        ) : (
          <span className="vd-shared-owner-unknown">Opened by ID</span>
        ),
    },
    {
      header: 'Access Level',
      key: 'access',
      render: () => (
        <div className="vd-readonly-badge">
          <Lock size={12} />
          <span>Read Only</span>
        </div>
      ),
    },
    {
      header: 'Size',
      key: 'file_size',
      render: (row) => formatFileSize(row.file_size),
    },
    {
      header: 'Shared Date',
      key: 'shared_at',
      render: (row) => formatDate(row.shared_at || row.created_at),
    },
    {
      header: 'Action',
      key: 'action',
      align: 'right',
      render: (row) => (
        <Button
          variant="ghost"
          size="sm"
          icon={Download}
          disabled={!hasStoredFile(row) || downloadingId === row.id}
          loading={downloadingId === row.id}
          onClick={() => handleDownloadSharedFile(row)}
        >
          Download
        </Button>
      ),
    },
  ];

  if (!isAuthenticated) {
    return (
      <div className="vd-shared-guest">
        <PageHeader title="Shared With Me" description="View documents shared with you by other users." />
        <Card elevation="sm" style={{ padding: '3rem', textAlign: 'center' }}>
          <h3>Authentication Required</h3>
          <p style={{ color: 'var(--color-text-muted)', margin: '1rem 0' }}>
            Please log in to view documents shared with your account.
          </p>
          <Button variant="primary" onClick={() => onOpenAuthModal('login')}>
            Sign In
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="vd-shared-page">
      <PageHeader
        title="Shared With Me"
        description="Documents other users have shared with your account in read-only mode."
        actions={
          <Button
            variant="outline"
            size="sm"
            icon={RefreshCw}
            loading={listLoading}
            onClick={fetchSharedList}
          >
            Refresh
          </Button>
        }
      />

      <Card
        title="Documents Shared With You"
        subtitle="Live from the server — recipients have read-only access"
        elevation="sm"
      >
        {listLoading ? (
          <div style={{ padding: '2rem 0', textAlign: 'center' }}>
            <Loader text="Loading shared documents..." />
          </div>
        ) : listError ? (
          <ErrorState
            title="Could not load shared documents"
            description={listError}
            onRetry={fetchSharedList}
          />
        ) : (
          <Table
            columns={columns}
            data={mergedDocs}
            emptyTitle="Nothing shared with you yet"
            emptyDescription="When another user shares a document with your email, it will appear here."
          />
        )}
        {manualDocs.length > 0 && (
          <div className="vd-shared-session-note">
            Includes {manualDocs.length} document{manualDocs.length === 1 ? '' : 's'} opened by ID
            this session.
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setManualDocs([])}
              aria-label="Clear manually opened documents"
            >
              Clear
            </Button>
          </div>
        )}
      </Card>

      <Card
        title="Open a Shared Document by ID"
        subtitle="Fallback lookup — adds the document to the list above for this session"
        elevation="sm"
        style={{ marginTop: '1.5rem' }}
      >
        <form onSubmit={handleFetchSharedDoc} className="vd-shared-lookup-form">
          <Input
            placeholder="Paste shared document UUID..."
            value={docIdInput}
            onChange={(e) => setDocIdInput(e.target.value)}
            icon={Search}
            required
          />
          <Button variant="primary" type="submit" icon={ShieldCheck} loading={lookupLoading}>
            Access Document
          </Button>
        </form>
      </Card>
    </div>
  );
};

export default SharedView;
