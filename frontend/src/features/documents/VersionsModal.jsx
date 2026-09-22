import React, { useState, useEffect, useCallback } from 'react';
import { Modal, Table, Button, Loader, ErrorState, useToast } from '../../shared/components';
import apiClient from '../../shared/services/apiClient';
import { Download, History, FileText } from 'lucide-react';
import './Modals.css';

export const VersionsModal = ({ isOpen, onClose, document }) => {
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [downloadingId, setDownloadingId] = useState(null);

  const toast = useToast();

  const fetchVersions = useCallback(async () => {
    if (!document?.id) return;
    setLoading(true);
    setError('');
    try {
      const data = await apiClient.get(`/documents/${document.id}/versions`);
      setVersions(data || []);
    } catch (err) {
      setError(err.message || 'Failed to load version history.');
    } finally {
      setLoading(false);
    }
  }, [document?.id]);

  useEffect(() => {
    if (isOpen && document?.id) {
      fetchVersions();
    }
  }, [isOpen, document?.id, fetchVersions]);

  const handleDownloadVersion = async (version) => {
    setDownloadingId(version.id);
    try {
      const token = localStorage.getItem('vaultdocs_token');
      const response = await fetch(`/v1/documents/${document.id}/versions/${version.id}/download`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });

      if (!response.ok) {
        throw new Error(`Download failed with status ${response.status}`);
      }

      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = version.original_filename || `version_${version.version_number}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);

      toast.success(`Downloaded version #${version.version_number}`);
    } catch (err) {
      toast.error(err.message || 'Download failed.', 'Error');
    } finally {
      setDownloadingId(null);
    }
  };

  const formatFileSize = (bytes) => {
    if (!bytes && bytes !== 0) return 'N/A';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (isoString) => {
    if (!isoString) return 'N/A';
    return new Date(isoString).toLocaleString();
  };

  const columns = [
    {
      header: 'Version',
      key: 'version_number',
      render: (row) => (
        <div className="vd-version-badge">
          <History size={14} />
          <span>v{row.version_number}</span>
        </div>
      ),
    },
    {
      header: 'Filename',
      key: 'original_filename',
      render: (row) => (
        <div className="vd-doc-cell">
          <FileText size={16} />
          <span>{row.original_filename}</span>
        </div>
      ),
    },
    {
      header: 'Size',
      key: 'file_size',
      render: (row) => formatFileSize(row.file_size),
    },
    {
      header: 'Created At',
      key: 'created_at',
      render: (row) => formatDate(row.created_at),
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
          loading={downloadingId === row.id}
          onClick={() => handleDownloadVersion(row)}
          aria-label={`Download version ${row.version_number}`}
        >
          Download
        </Button>
      ),
    },
  ];

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Version History — ${document?.name || 'Document'}`}
      size="lg"
    >
      {loading ? (
        <div style={{ padding: '2rem 0', textAlign: 'center' }}>
          <Loader text="Loading version history..." />
        </div>
      ) : error ? (
        <ErrorState
          title="Could not load versions"
          description={error}
          onRetry={fetchVersions}
        />
      ) : (
        <Table
          columns={columns}
          data={versions}
          emptyTitle="No versions recorded"
          emptyDescription="Upload files to create version history."
        />
      )}
    </Modal>
  );
};

export default VersionsModal;
