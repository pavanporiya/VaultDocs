import React, { useState, useEffect, useCallback, useRef } from 'react';
import {
  PageHeader,
  Card,
  Table,
  Button,
  Input,
  Select,
  Modal,
  Loader,
  ErrorState,
  useToast,
} from '../../shared/components';
import { useAuth } from '../../shared/context/AuthContext';
import apiClient, { downloadFile, saveBlob } from '../../shared/services/apiClient';
import VersionsModal from './VersionsModal';
import SharesModal from './SharesModal';
import UploadModal from './UploadModal';
import { formatFileSize, formatDate, hasStoredFile, getDocumentDisplayName } from '../../shared/utils/format';
import {
  FileText,
  Plus,
  Upload,
  Download,
  Trash2,
  History,
  Share2,
  Search,
} from 'lucide-react';
import './DocumentsView.css';

const SEARCH_DEBOUNCE_MS = 400;

export const DocumentsView = ({ onOpenAuthModal, onNavigate, searchQuery = '' }) => {
  const { isAuthenticated } = useAuth();
  const [documents, setDocuments] = useState([]);
  const [folders, setFolders] = useState([]);
  const [localSearch, setLocalSearch] = useState(searchQuery);
  const [debouncedSearch, setDebouncedSearch] = useState(searchQuery);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [isSearching, setIsSearching] = useState(false);

  // Modals state
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isVersionsModalOpen, setIsVersionsModalOpen] = useState(false);
  const [isSharesModalOpen, setIsSharesModalOpen] = useState(false);
  const [activeDocForModal, setActiveDocForModal] = useState(null);
  const [downloadingId, setDownloadingId] = useState(null);

  // Upload modal state (shared UploadModal)
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [selectedDocForUpload, setSelectedDocForUpload] = useState(null);
  const [uploadMode, setUploadMode] = useState('POST'); // 'POST' or 'PUT'

  // Create form state
  const [docName, setDocName] = useState('');
  const [selectedFolderId, setSelectedFolderId] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const toast = useToast();

  // Debounce the search term so typing hits the real search endpoint calmly.
  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(localSearch), SEARCH_DEBOUNCE_MS);
    return () => clearTimeout(timer);
  }, [localSearch]);

  // Sync when the NAVBAR search changes (typing there while already on this
  // page). Local edits never touch the prop, so this cannot loop.
  const lastNavQueryRef = useRef(searchQuery);
  useEffect(() => {
    if (searchQuery !== lastNavQueryRef.current) {
      lastNavQueryRef.current = searchQuery;
      setLocalSearch(searchQuery);
      setDebouncedSearch(searchQuery); // external input skips the debounce
    }
  }, [searchQuery]);

  const fetchDocuments = useCallback(async () => {
    if (!isAuthenticated) return;
    const searchTerm = debouncedSearch;
    const isSearch = Boolean(searchTerm && searchTerm.trim());
    if (isSearch) {
      setIsSearching(true);
    } else {
      setLoading(true);
    }
    setError('');
    try {
      const endpoint = isSearch
        ? `/documents/search?q=${encodeURIComponent(searchTerm.trim())}`
        : '/documents';
      // Fetch docs first; folders only matter for the create modal / folder column.
      const docsData = await apiClient.get(endpoint);
      // Defense-in-depth: never render owner-only quick actions for rows the
      // API marks as non-owner (e.g. if shared docs ever appear here).
      setDocuments(
        (docsData || []).map((d) =>
          d.is_owner === false
            ? {
                ...d,
                can_edit: d.can_edit ?? false,
                can_share: d.can_share ?? false,
                can_delete: d.can_delete ?? false,
              }
            : d
        )
      );
    } catch (err) {
      setError(err.message || 'Failed to load documents.');
    } finally {
      setLoading(false);
      setIsSearching(false);
    }
  }, [isAuthenticated, debouncedSearch]);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  // Folder list is only needed for the create modal; load it lazily once.
  useEffect(() => {
    if (!isAuthenticated || !isCreateModalOpen || folders.length > 0) return;
    let cancelled = false;
    apiClient
      .get('/folders')
      .then((data) => {
        if (!cancelled) setFolders(data || []);
      })
      .catch(() => {
        if (!cancelled) setFolders([]);
      });
    return () => {
      cancelled = true;
    };
  }, [isAuthenticated, isCreateModalOpen, folders.length]);

  const handleSearchChange = (e) => {
    setLocalSearch(e.target.value);
  };

  const clearSearch = () => {
    setLocalSearch('');
  };

  const handleCreateDocument = async (e) => {
    e.preventDefault();
    if (!docName.trim()) return;

    setSubmitting(true);
    try {
      const payload = {
        name: docName.trim(),
        folder_id: selectedFolderId || null,
      };
      const newDoc = await apiClient.post('/documents', payload);
      toast.success(`Document "${newDoc.name}" created! Now upload a file.`);
      setDocName('');
      setSelectedFolderId('');
      setIsCreateModalOpen(false);

      // Automatically open file upload modal for new document
      setSelectedDocForUpload(newDoc);
      setUploadMode('POST');
      setIsUploadModalOpen(true);
      await fetchDocuments();
    } catch (err) {
      toast.error(err.message || 'Failed to create document.', 'Error');
    } finally {
      setSubmitting(false);
    }
  };

  // Centralized authenticated download via the shared apiClient helper.
  const handleDownloadCurrentFile = async (doc) => {
    if (doc.can_download === false) {
      toast.error('Download disabled: View-only access.', 'Download Error');
      return;
    }
    setDownloadingId(doc.id);
    try {
      const { blob, filename } = await downloadFile(`/documents/${doc.id}/download`);
      saveBlob(blob, filename || getDocumentDisplayName(doc));
      toast.success(`Downloaded "${filename || doc.name}"`);
    } catch (err) {
      const message =
        err?.status === 404
          ? 'No file has been uploaded for this document yet.'
          : err.message || 'Failed to download file.';
      toast.error(message, 'Download Error');
    } finally {
      setDownloadingId(null);
    }
  };

  const handleDeleteDocument = async (doc) => {
    if (!window.confirm(`Are you sure you want to delete document "${doc.name}"?`)) {
      return;
    }
    try {
      await apiClient.delete(`/documents/${doc.id}`);
      toast.success(`Document "${doc.name}" deleted.`);
      await fetchDocuments();
    } catch (err) {
      toast.error(err.message || 'Failed to delete document.', 'Error');
    }
  };

  const openDocumentDetail = (doc) => {
    if (onNavigate) onNavigate(`/documents/${doc.id}`);
  };

  const folderOptions = [
    { value: '', label: 'Root (No Folder)' },
    ...folders.map((f) => ({ value: f.id, label: f.name })),
  ];

  const columns = [
    {
      header: 'Document Name',
      key: 'name',
      render: (row) => (
        <button
          type="button"
          className="vd-doc-title-cell vd-doc-link"
          onClick={() => openDocumentDetail(row)}
          title="Open document details"
        >
          <FileText size={18} className="vd-doc-icon" />
          <span className="vd-doc-name">{row.name}</span>
        </button>
      ),
    },
    {
      header: 'Original File',
      key: 'original_filename',
      render: (row) => row.original_filename || <span className="vd-no-file-text">No File</span>,
    },
    {
      header: 'Size',
      key: 'file_size',
      render: (row) => formatFileSize(row.file_size),
    },
    {
      header: 'Folder',
      key: 'folder_id',
      render: (row) => {
        if (!row.folder_id) return 'Root';
        const folder = folders.find((f) => f.id === row.folder_id);
        return folder ? folder.name : 'Folder';
      },
    },
    {
      header: 'Updated',
      key: 'updated_at',
      render: (row) => formatDate(row.updated_at),
    },
    {
      header: 'Actions',
      key: 'actions',
      align: 'right',
      render: (row) => (
        <div className="vd-doc-actions" onClick={(e) => e.stopPropagation()}>
          <Button
            variant="ghost"
            size="sm"
            icon={Download}
            title={
              row.can_download === false
                ? 'Download disabled: View-only access'
                : hasStoredFile(row)
                  ? 'Download File'
                  : 'No file uploaded yet'
            }
            disabled={row.can_download === false || !hasStoredFile(row) || downloadingId === row.id}
            loading={downloadingId === row.id}
            onClick={() => handleDownloadCurrentFile(row)}
          />
          {/* Owner-only actions: hidden for viewer/editor rows. This list is
              owner-scoped from the backend, so flags are normally absent
              (owner-shaped) — the guards are defense-in-depth for shared rows. */}
          {row.can_edit !== false && (
            <Button
              variant="ghost"
              size="sm"
              icon={Upload}
              title={hasStoredFile(row) ? 'Replace File (New Version)' : 'Upload File'}
              onClick={() => {
                setSelectedDocForUpload(row);
                setUploadMode(hasStoredFile(row) ? 'PUT' : 'POST');
                setIsUploadModalOpen(true);
              }}
            />
          )}
          <Button
            variant="ghost"
            size="sm"
            icon={History}
            title="Version History"
            disabled={!hasStoredFile(row)}
            onClick={() => {
              setActiveDocForModal(row);
              setIsVersionsModalOpen(true);
            }}
          />
          {row.can_share !== false && (
            <Button
              variant="ghost"
              size="sm"
              icon={Share2}
              title="Share Document"
              onClick={() => {
                setActiveDocForModal(row);
                setIsSharesModalOpen(true);
              }}
            />
          )}
          {row.can_delete !== false && (
            <Button
              variant="danger"
              size="sm"
              icon={Trash2}
              title="Delete Document"
              onClick={() => handleDeleteDocument(row)}
            />
          )}
        </div>
      ),
    },
  ];

  const isSearchActive = Boolean(debouncedSearch.trim());

  if (!isAuthenticated) {
    return (
      <div className="vd-docs-guest">
        <PageHeader title="All Documents" description="Manage user documents, files, versions, and shares." />
        <Card elevation="sm" style={{ padding: '3rem', textAlign: 'center' }}>
          <h3>Authentication Required</h3>
          <p style={{ color: 'var(--color-text-muted)', margin: '1rem 0' }}>
            Please log in to manage your documents and files.
          </p>
          <Button variant="primary" onClick={() => onOpenAuthModal('login')}>
            Sign In
          </Button>
        </Card>
      </div>
    );
  }

  return (
    <div className="vd-documents-page">
      <PageHeader
        title="All Documents"
        description="Create document records, upload & replace files, maintain versions, and share access."
        actions={
          <Button
            variant="primary"
            icon={Plus}
            onClick={() => {
              setDocName('');
              setSelectedFolderId('');
              setIsCreateModalOpen(true);
            }}
          >
            New Document
          </Button>
        }
      />

      <Card elevation="sm">
        {/* Search Bar — hits the real /documents/search endpoint (debounced) */}
        <div className="vd-docs-search-bar">
          <Input
            placeholder="Search documents by name..."
            value={localSearch}
            onChange={handleSearchChange}
            icon={Search}
            type="search"
            aria-label="Search documents by name"
          />
          {isSearching && <span className="vd-docs-searching">Searching…</span>}
          {localSearch && (
            <Button variant="ghost" size="sm" onClick={clearSearch}>
              Clear
            </Button>
          )}
        </div>

        {loading ? (
          <div style={{ padding: '3rem 0', textAlign: 'center' }}>
            <Loader text={isSearchActive ? 'Searching documents...' : 'Loading documents...'} />
          </div>
        ) : error ? (
          <ErrorState
            title={isSearchActive ? 'Search failed' : 'Could not fetch documents'}
            description={error}
            onRetry={fetchDocuments}
          />
        ) : (
          <Table
            columns={columns}
            data={documents}
            emptyTitle={isSearchActive ? 'No matching documents' : 'No documents found'}
            emptyDescription={
              isSearchActive
                ? `No documents matching "${debouncedSearch}"`
                : 'Click "New Document" to create your first document.'
            }
          />
        )}
      </Card>

      {/* Create Document Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title="Create New Document"
        size="sm"
      >
        <form onSubmit={handleCreateDocument} className="vd-form">
          <Input
            label="Document Name"
            placeholder="e.g. Q3 Financial Statement"
            value={docName}
            onChange={(e) => setDocName(e.target.value)}
            required
            autoFocus
          />
          <Select
            label="Assign to Folder (Optional)"
            value={selectedFolderId}
            onChange={(e) => setSelectedFolderId(e.target.value)}
            options={folderOptions}
          />
          <div className="vd-modal-footer">
            <Button
              variant="secondary"
              type="button"
              onClick={() => setIsCreateModalOpen(false)}
            >
              Cancel
            </Button>
            <Button variant="primary" type="submit" loading={submitting}>
              Create Document
            </Button>
          </div>
        </form>
      </Modal>

      {/* Upload / Replace File Modal (shared component) */}
      <UploadModal
        isOpen={isUploadModalOpen}
        document={selectedDocForUpload}
        mode={uploadMode}
        onClose={() => setIsUploadModalOpen(false)}
        onUploaded={() => fetchDocuments()}
      />

      {/* Version History Modal */}
      <VersionsModal
        isOpen={isVersionsModalOpen}
        onClose={() => setIsVersionsModalOpen(false)}
        document={activeDocForModal}
      />

      {/* Shares Modal */}
      <SharesModal
        isOpen={isSharesModalOpen}
        onClose={() => setIsSharesModalOpen(false)}
        document={activeDocForModal}
      />
    </div>
  );
};

export default DocumentsView;
