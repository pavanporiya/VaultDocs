import React, { useState, useEffect, useCallback } from 'react';
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
import apiClient from '../../shared/services/apiClient';
import VersionsModal from './VersionsModal';
import SharesModal from './SharesModal';
import {
  FileText,
  Plus,
  Upload,
  Download,
  Trash2,
  History,
  Share2,
  RefreshCw,
  Search,
} from 'lucide-react';
import './DocumentsView.css';

export const DocumentsView = ({ onOpenAuthModal, searchQuery = '' }) => {
  const { isAuthenticated } = useAuth();
  const [documents, setDocuments] = useState([]);
  const [folders, setFolders] = useState([]);
  const [localSearch, setLocalSearch] = useState(searchQuery);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Modals state
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isUploadModalOpen, setIsUploadModalOpen] = useState(false);
  const [selectedDocForUpload, setSelectedDocForUpload] = useState(null);
  const [uploadMode, setUploadMode] = useState('POST'); // 'POST' or 'PUT'

  const [isVersionsModalOpen, setIsVersionsModalOpen] = useState(false);
  const [isSharesModalOpen, setIsSharesModalOpen] = useState(false);
  const [activeDocForModal, setActiveDocForModal] = useState(null);

  // Form states
  const [docName, setDocName] = useState('');
  const [selectedFolderId, setSelectedFolderId] = useState('');
  const [selectedFile, setSelectedFile] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const toast = useToast();

  const fetchDocuments = useCallback(async () => {
    if (!isAuthenticated) return;
    setLoading(true);
    setError('');
    try {
      let endpoint = '/documents';
      const searchTerm = localSearch || searchQuery;
      if (searchTerm && searchTerm.trim()) {
        endpoint = `/documents/search?q=${encodeURIComponent(searchTerm.trim())}`;
      }
      const [docsData, foldersData] = await Promise.all([
        apiClient.get(endpoint),
        apiClient.get('/folders'),
      ]);
      setDocuments(docsData || []);
      setFolders(foldersData || []);
    } catch (err) {
      setError(err.message || 'Failed to load documents.');
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated, localSearch, searchQuery]);

  useEffect(() => {
    fetchDocuments();
  }, [fetchDocuments]);

  // Handle Search Input Change
  const handleSearchChange = (e) => {
    setLocalSearch(e.target.value);
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

  const handleFileUpload = async (e) => {
    e.preventDefault();
    if (!selectedFile || !selectedDocForUpload) {
      toast.error('Please select a file to upload.', 'Validation Error');
      return;
    }

    setSubmitting(true);
    try {
      const formData = new FormData();
      formData.append('file', selectedFile);

      const endpoint = `/documents/${selectedDocForUpload.id}/upload`;
      if (uploadMode === 'PUT') {
        await apiClient.put(endpoint, formData);
        toast.success(`Replaced file for "${selectedDocForUpload.name}"!`);
      } else {
        await apiClient.upload(endpoint, formData);
        toast.success(`File uploaded for "${selectedDocForUpload.name}"!`);
      }

      setSelectedFile(null);
      setSelectedDocForUpload(null);
      setIsUploadModalOpen(false);
      await fetchDocuments();
    } catch (err) {
      toast.error(err.message || 'File upload failed.', 'Upload Error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleDownloadCurrentFile = async (doc) => {
    try {
      const token = localStorage.getItem('vaultdocs_token');
      const response = await fetch(`/v1/documents/${doc.id}/download`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });

      if (!response.ok) {
        if (response.status === 404) {
          throw new Error('No file has been uploaded for this document yet.');
        }
        throw new Error(`Download failed with status ${response.status}`);
      }

      const blob = await response.blob();
      const contentDisposition = response.headers.get('content-disposition') || '';
      const filenameMatch = contentDisposition.match(/filename="?([^"]+)"?/);
      const filename = filenameMatch ? filenameMatch[1] : doc.original_filename || doc.name;

      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      toast.success(`Downloaded "${filename}"`);
    } catch (err) {
      toast.error(err.message || 'Failed to download file.', 'Download Error');
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

  const formatFileSize = (bytes) => {
    if (!bytes && bytes !== 0) return 'No File';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
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
        <div className="vd-doc-title-cell">
          <FileText size={18} className="vd-doc-icon" />
          <span className="vd-doc-name">{row.name}</span>
        </div>
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
      header: 'Actions',
      key: 'actions',
      align: 'right',
      render: (row) => (
        <div className="vd-doc-actions" onClick={(e) => e.stopPropagation()}>
          <Button
            variant="ghost"
            size="sm"
            icon={Download}
            title="Download File"
            disabled={!row.file_path}
            onClick={() => handleDownloadCurrentFile(row)}
          />
          <Button
            variant="ghost"
            size="sm"
            icon={row.file_path ? RefreshCw : Upload}
            title={row.file_path ? 'Replace File (New Version)' : 'Upload File'}
            onClick={() => {
              setSelectedDocForUpload(row);
              setUploadMode(row.file_path ? 'PUT' : 'POST');
              setSelectedFile(null);
              setIsUploadModalOpen(true);
            }}
          />
          <Button
            variant="ghost"
            size="sm"
            icon={History}
            title="Version History"
            disabled={!row.file_path}
            onClick={() => {
              setActiveDocForModal(row);
              setIsVersionsModalOpen(true);
            }}
          />
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
          <Button
            variant="danger"
            size="sm"
            icon={Trash2}
            title="Delete Document"
            onClick={() => handleDeleteDocument(row)}
          />
        </div>
      ),
    },
  ];

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
        {/* Search Bar */}
        <div className="vd-docs-search-bar">
          <Input
            placeholder="Search documents by name..."
            value={localSearch}
            onChange={handleSearchChange}
            icon={Search}
          />
        </div>

        {loading ? (
          <div style={{ padding: '3rem 0', textAlign: 'center' }}>
            <Loader text="Loading documents..." />
          </div>
        ) : error ? (
          <ErrorState
            title="Could not fetch documents"
            description={error}
            onRetry={fetchDocuments}
          />
        ) : (
          <Table
            columns={columns}
            data={documents}
            emptyTitle="No documents found"
            emptyDescription={
              localSearch
                ? `No documents matching "${localSearch}"`
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

      {/* Upload / Replace File Modal */}
      <Modal
        isOpen={isUploadModalOpen}
        onClose={() => setIsUploadModalOpen(false)}
        title={
          uploadMode === 'PUT'
            ? `Replace File (New Version) — ${selectedDocForUpload?.name}`
            : `Upload File — ${selectedDocForUpload?.name}`
        }
        size="sm"
      >
        <form onSubmit={handleFileUpload} className="vd-form">
          <div className="vd-file-input-group">
            <label className="vd-file-label">Select File to Upload</label>
            <input
              type="file"
              className="vd-file-input"
              onChange={(e) => setSelectedFile(e.target.files[0] || null)}
              required
            />
            {selectedFile && (
              <span className="vd-selected-file-info">
                Selected: {selectedFile.name} ({formatFileSize(selectedFile.size)})
              </span>
            )}
          </div>
          {uploadMode === 'PUT' && (
            <span className="vd-replace-note">
              Uploading a replacement file creates a new document version automatically while preserving historical versions.
            </span>
          )}
          <div className="vd-modal-footer">
            <Button
              variant="secondary"
              type="button"
              onClick={() => setIsUploadModalOpen(false)}
            >
              Cancel
            </Button>
            <Button
              variant="primary"
              type="submit"
              icon={Upload}
              loading={submitting}
              disabled={!selectedFile}
            >
              {uploadMode === 'PUT' ? 'Upload Replacement' : 'Upload File'}
            </Button>
          </div>
        </form>
      </Modal>

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
