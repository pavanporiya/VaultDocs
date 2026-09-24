import React, { useState, useEffect, useCallback } from 'react';
import {
  PageHeader,
  Card,
  Table,
  Button,
  Input,
  Modal,
  Loader,
  EmptyState,
  ErrorState,
  useToast,
} from '../../shared/components';
import { useAuth } from '../../shared/context/AuthContext';
import apiClient from '../../shared/services/apiClient';
import { formatFileSize, formatDate } from '../../shared/utils/format';
import {
  FolderOpen,
  FolderPlus,
  FileText,
  Trash2,
  Edit2,
  ChevronRight,
  Folder,
} from 'lucide-react';
import './ExplorerView.css';

export const ExplorerView = ({ onOpenAuthModal, onNavigate }) => {
  const { isAuthenticated } = useAuth();
  const [folders, setFolders] = useState([]);
  const [currentFolder, setCurrentFolder] = useState(null); // null = root
  const [folderPath, setFolderPath] = useState([]); // breadcrumbs
  const [folderDocs, setFolderDocs] = useState([]);

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Folder Modal states
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [isEditModalOpen, setIsEditModalOpen] = useState(false);
  const [newFolderName, setNewFolderName] = useState('');
  const [editingFolder, setEditingFolder] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  const toast = useToast();

  const fetchFoldersAndDocs = useCallback(async () => {
    if (!isAuthenticated) return;
    setLoading(true);
    setError('');
    try {
      const allFolders = await apiClient.get('/folders');
      setFolders(allFolders || []);

      if (currentFolder) {
        const docs = await apiClient.get(`/documents/search?folder_id=${currentFolder.id}`);
        setFolderDocs(docs || []);
      } else {
        const allDocs = await apiClient.get('/documents');
        // Root documents (folder_id is null)
        setFolderDocs((allDocs || []).filter((d) => !d.folder_id));
      }
    } catch (err) {
      setError(err.message || 'Failed to load folder structure.');
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated, currentFolder]);

  useEffect(() => {
    fetchFoldersAndDocs();
  }, [fetchFoldersAndDocs]);

  const handleCreateFolder = async (e) => {
    e.preventDefault();
    if (!newFolderName.trim()) return;

    setSubmitting(true);
    try {
      await apiClient.post('/folders', {
        name: newFolderName.trim(),
        parent_id: currentFolder ? currentFolder.id : null,
      });
      toast.success(`Folder "${newFolderName.trim()}" created successfully!`);
      setNewFolderName('');
      setIsCreateModalOpen(false);
      await fetchFoldersAndDocs();
    } catch (err) {
      toast.error(err.message || 'Failed to create folder.', 'Folder Error');
    } finally {
      setSubmitting(false);
    }
  };

  const handleRenameFolder = async (e) => {
    e.preventDefault();
    if (!editingFolder || !newFolderName.trim()) return;

    setSubmitting(true);
    try {
      await apiClient.patch(`/folders/${editingFolder.id}`, {
        name: newFolderName.trim(),
      });
      toast.success('Folder renamed successfully!');
      setEditingFolder(null);
      setNewFolderName('');
      setIsEditModalOpen(false);
      await fetchFoldersAndDocs();
    } catch (err) {
      toast.error(err.message || 'Failed to rename folder.', 'Error');
    } finally {
      setSubmitting(false);
    }
  };

  const navigateToFolder = (folder) => {
    if (!folder) {
      setCurrentFolder(null);
      setFolderPath([]);
    } else {
      setCurrentFolder(folder);
      setFolderPath((prev) => [...prev, folder]);
    }
  };

  const handleDeleteFolder = async (folder) => {
    if (!window.confirm(`Are you sure you want to delete folder "${folder.name}"?`)) {
      return;
    }
    try {
      await apiClient.delete(`/folders/${folder.id}`);
      toast.success(`Folder "${folder.name}" deleted.`);
      // If the deleted folder is open (or an ancestor of it), fall back to root
      // so the explorer never points at a now-nonexistent folder.
      if (currentFolder) {
        const isDeleted = currentFolder.id === folder.id;
        const isDescendant = folderPath.some((f) => f.id === folder.id);
        if (isDeleted || isDescendant) {
          setCurrentFolder(null);
          setFolderPath([]);
        }
      }
      await fetchFoldersAndDocs();
    } catch (err) {
      toast.error(err.message || 'Failed to delete folder.', 'Error');
    }
  };

  const openDocumentDetail = (doc) => {
    if (onNavigate) onNavigate(`/documents/${doc.id}`);
  };

  // Filter subfolders for current folder
  const currentSubfolders = folders.filter((f) =>
    currentFolder ? f.parent_id === currentFolder.id : !f.parent_id
  );

  if (!isAuthenticated) {
    return (
      <div className="vd-explorer-guest">
        <PageHeader title="Folder Explorer" description="Manage hierarchical folders and documents." />
        <Card elevation="sm" style={{ padding: '3rem', textAlign: 'center' }}>
          <h3>Authentication Required</h3>
          <p style={{ color: 'var(--color-text-muted)', margin: '1rem 0' }}>
            Please log in to view and manage your folder structure.
          </p>
          <Button variant="primary" onClick={() => onOpenAuthModal('login')}>
            Sign In
          </Button>
        </Card>
      </div>
    );
  }

  const breadcrumbs = [
    { label: 'Root Vault', onClick: () => navigateToFolder(null) },
    ...folderPath.map((f, idx) => ({
      label: f.name,
      onClick: () => {
        const newPath = folderPath.slice(0, idx + 1);
        setFolderPath(newPath);
        setCurrentFolder(f);
      },
    })),
  ];

  const docColumns = [
    {
      header: 'Document Name',
      key: 'name',
      render: (row) => (
        <button
          type="button"
          className="vd-explorer-doc-cell vd-explorer-doc-link"
          onClick={() => openDocumentDetail(row)}
          title="Open document details"
        >
          <FileText size={18} className="vd-explorer-doc-icon" />
          <span className="vd-explorer-doc-name">{row.name}</span>
        </button>
      ),
    },
    {
      header: 'Original File',
      key: 'original_filename',
      render: (row) => row.original_filename || '—',
    },
    {
      header: 'Size',
      key: 'file_size',
      render: (row) => formatFileSize(row.file_size),
    },
    {
      header: 'Created',
      key: 'created_at',
      render: (row) => formatDate(row.created_at),
    },
  ];

  return (
    <div className="vd-explorer">
      <PageHeader
        title="Folder Explorer"
        description="Organize documents into nested hierarchical folders."
        breadcrumbs={breadcrumbs}
        actions={
          <Button
            variant="primary"
            icon={FolderPlus}
            onClick={() => {
              setNewFolderName('');
              setIsCreateModalOpen(true);
            }}
          >
            Create Folder
          </Button>
        }
      />

      {loading ? (
        <div style={{ padding: '3rem 0', textAlign: 'center' }}>
          <Loader text="Loading folder contents..." />
        </div>
      ) : error ? (
        <ErrorState
          title="Could not load folders"
          description={error}
          onRetry={fetchFoldersAndDocs}
        />
      ) : (
        <>
          {/* Subfolders Grid */}
          <Card
            title={`Subfolders ${currentFolder ? `in "${currentFolder.name}"` : '(Root)'}`}
            elevation="sm"
          >
            {currentSubfolders.length === 0 ? (
              <div className="vd-empty-subfolders">
                <Folder size={32} className="vd-empty-subfolders-icon" />
                <span>No subfolders in this location.</span>
              </div>
            ) : (
              <div className="vd-folders-grid">
                {currentSubfolders.map((folder) => (
                  <div
                    key={folder.id}
                    className="vd-folder-card"
                    role="button"
                    tabIndex={0}
                    aria-label={`Open folder ${folder.name}`}
                    onClick={() => navigateToFolder(folder)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' || e.key === ' ') {
                        e.preventDefault();
                        navigateToFolder(folder);
                      }
                    }}
                  >
                    <div className="vd-folder-card-header">
                      <div className="vd-folder-icon-wrap">
                        <FolderOpen size={24} />
                      </div>
                      <div className="vd-folder-actions" onClick={(e) => e.stopPropagation()}>
                        <button
                          type="button"
                          className="vd-folder-act-btn"
                          title="Rename Folder"
                          aria-label={`Rename folder ${folder.name}`}
                          onClick={() => {
                            setEditingFolder(folder);
                            setNewFolderName(folder.name);
                            setIsEditModalOpen(true);
                          }}
                        >
                          <Edit2 size={14} />
                        </button>
                        <button
                          type="button"
                          className="vd-folder-act-btn vd-folder-act-btn--danger"
                          title="Delete Folder"
                          aria-label={`Delete folder ${folder.name}`}
                          onClick={() => handleDeleteFolder(folder)}
                        >
                          <Trash2 size={14} />
                        </button>
                      </div>
                    </div>
                    <div className="vd-folder-card-body">
                      <span className="vd-folder-name">{folder.name}</span>
                      <ChevronRight size={16} className="vd-folder-arrow" />
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>

          {/* Folder Documents */}
          <Card
            title={`Documents ${currentFolder ? `in "${currentFolder.name}"` : '(Root Level)'}`}
            elevation="sm"
            style={{ marginTop: '1.5rem' }}
          >
            <Table
              columns={docColumns}
              data={folderDocs}
              emptyTitle="No documents in this folder"
              emptyDescription="Upload or assign documents to this folder."
            />
          </Card>
        </>
      )}

      {/* Document editing happens in the document workspace at /documents/:id */}

      {/* Create Folder Modal */}
      <Modal
        isOpen={isCreateModalOpen}
        onClose={() => setIsCreateModalOpen(false)}
        title={currentFolder ? `Create Subfolder in "${currentFolder.name}"` : 'Create Root Folder'}
        size="sm"
      >
        <form onSubmit={handleCreateFolder}>
          <Input
            label="Folder Name"
            placeholder="e.g. Financial Reports 2026"
            value={newFolderName}
            onChange={(e) => setNewFolderName(e.target.value)}
            required
            autoFocus
          />
          <div className="vd-explorer-modal-footer">
            <Button
              variant="secondary"
              type="button"
              onClick={() => setIsCreateModalOpen(false)}
            >
              Cancel
            </Button>
            <Button variant="primary" type="submit" loading={submitting}>
              Create
            </Button>
          </div>
        </form>
      </Modal>

      {/* Rename Folder Modal */}
      <Modal
        isOpen={isEditModalOpen}
        onClose={() => setIsEditModalOpen(false)}
        title="Rename Folder"
        size="sm"
      >
        <form onSubmit={handleRenameFolder}>
          <Input
            label="Folder Name"
            value={newFolderName}
            onChange={(e) => setNewFolderName(e.target.value)}
            required
            autoFocus
          />
          <div className="vd-explorer-modal-footer">
            <Button
              variant="secondary"
              type="button"
              onClick={() => setIsEditModalOpen(false)}
            >
              Cancel
            </Button>
            <Button variant="primary" type="submit" loading={submitting}>
              Save
            </Button>
          </div>
        </form>
      </Modal>
    </div>
  );
};

export default ExplorerView;
