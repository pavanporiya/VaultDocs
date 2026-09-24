import React, { useState, useEffect, useCallback } from 'react';
import { Modal, Table, Button, Loader, ErrorState, useToast } from '../../shared/components';
import apiClient, { downloadFile, saveBlob } from '../../shared/services/apiClient';
import { formatFileSize, formatDate } from '../../shared/utils/format';
import { Download, History, FileText, Info, X, Lock } from 'lucide-react';
import './Modals.css';

/**
 * Version History modal.
 *
 * Data is fetched live from the backend:
 * - GET /documents/{id}/versions                list
 * - GET /documents/{id}/versions/{version_id}   details for the drawer
 * - GET /documents/{id}/versions/{version_id}/download  file download
 *
 * Permission gating (server-authoritative flags on the document record):
 * - can_download === false  -> "Download Version" buttons are hidden and the
 *   handler refuses to fire (view-only / "seen" shares; backend enforces 403).
 * - There are no rollback/upload controls here by design: new versions are
 *   created only via the owner-only Upload / Replace flow.
 */
export const VersionsModal = ({ isOpen, onClose, document }) => {
  const [versions, setVersions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [downloadingId, setDownloadingId] = useState(null);

  // Version details drawer
  const [detailsVersion, setDetailsVersion] = useState(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [detailsError, setDetailsError] = useState('');

  const toast = useToast();

  // Legacy responses without flags default to owner-shaped permissions so
  // existing owner flows are never broken.
  const canDownload = document?.can_download !== false;

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
      setDetailsVersion(null);
    }
  }, [isOpen, document?.id, fetchVersions]);

  const handleDownloadVersion = async (version) => {
    if (!canDownload) {
      toast.error('Download disabled: View-only access.', 'Permission Denied');
      return;
    }
    setDownloadingId(version.id);
    try {
      const { blob, filename } = await downloadFile(
        `/documents/${document.id}/versions/${version.id}/download`
      );
      saveBlob(blob, filename || version.original_filename || `version_${version.version_number}`);
      toast.success(`Downloaded version #${version.version_number}`);
    } catch (err) {
      toast.error(err.message || 'Download failed.', 'Error');
    } finally {
      setDownloadingId(null);
    }
  };

  const openVersionDetails = async (version) => {
    setDetailsVersion(version); // show list data immediately
    setDetailsError('');
    setDetailsLoading(true);
    try {
      // Fetch authoritative version details from the backend.
      const fresh = await apiClient.get(`/documents/${document.id}/versions/${version.id}`);
      setDetailsVersion(fresh);
    } catch (err) {
      setDetailsError(err.message || 'Could not load version details.');
    } finally {
      setDetailsLoading(false);
    }
  };

  const closeDetails = () => {
    setDetailsVersion(null);
    setDetailsError('');
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
        <button
          type="button"
          className="vd-version-link"
          onClick={() => openVersionDetails(row)}
          title="View version details"
        >
          <FileText size={16} />
          <span>{row.original_filename}</span>
        </button>
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
      render: (row) => formatDate(row.created_at, { withTime: true }),
    },
    {
      header: 'Action',
      key: 'action',
      align: 'right',
      render: (row) => (
        <div className="vd-version-actions">
          <Button
            variant="ghost"
            size="sm"
            icon={Info}
            title="Version details"
            aria-label={`View details for version ${row.version_number}`}
            onClick={() => openVersionDetails(row)}
          />
          {canDownload ? (
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
          ) : (
            <span className="vd-version-locked" title="Download disabled: View-only access">
              <Lock size={14} />
              Locked
            </span>
          )}
        </div>
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

      {/* Version details drawer */}
      {detailsVersion && (
        <div
          className="vd-version-drawer-overlay"
          onClick={closeDetails}
          role="presentation"
        >
          <div
            className="vd-version-drawer"
            role="dialog"
            aria-modal="true"
            aria-label={`Details for version ${detailsVersion.version_number}`}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="vd-version-drawer-header">
              <h4 className="vd-version-drawer-title">
                Version Details — v{detailsVersion.version_number}
              </h4>
              <button
                type="button"
                className="vd-version-drawer-close"
                onClick={closeDetails}
                aria-label="Close version details"
              >
                <X size={18} />
              </button>
            </div>

            {detailsLoading ? (
              <div style={{ padding: '1.5rem 0', textAlign: 'center' }}>
                <Loader text="Loading version details..." />
              </div>
            ) : detailsError ? (
              <ErrorState
                title="Could not load version details"
                description={detailsError}
                onRetry={() => openVersionDetails(detailsVersion)}
              />
            ) : (
              <div className="vd-version-drawer-body">
                <div className="vd-version-detail-row">
                  <span className="vd-version-detail-label">Version Number</span>
                  <span className="vd-version-detail-value">v{detailsVersion.version_number}</span>
                </div>
                <div className="vd-version-detail-row">
                  <span className="vd-version-detail-label">Version ID</span>
                  <span className="vd-version-detail-value vd-version-detail-mono">
                    {detailsVersion.id}
                  </span>
                </div>
                <div className="vd-version-detail-row">
                  <span className="vd-version-detail-label">Original Filename</span>
                  <span className="vd-version-detail-value">{detailsVersion.original_filename}</span>
                </div>
                <div className="vd-version-detail-row">
                  <span className="vd-version-detail-label">File Size</span>
                  <span className="vd-version-detail-value">
                    {formatFileSize(detailsVersion.file_size)}
                  </span>
                </div>
                <div className="vd-version-detail-row">
                  <span className="vd-version-detail-label">Content Type</span>
                  <span className="vd-version-detail-value">{detailsVersion.content_type}</span>
                </div>
                <div className="vd-version-detail-row">
                  <span className="vd-version-detail-label">Created At</span>
                  <span className="vd-version-detail-value">
                    {formatDate(detailsVersion.created_at, { withTime: true })}
                  </span>
                </div>
                <div className="vd-version-drawer-footer">
                  {canDownload ? (
                    <Button
                      variant="primary"
                      size="sm"
                      icon={Download}
                      loading={downloadingId === detailsVersion.id}
                      onClick={() => handleDownloadVersion(detailsVersion)}
                    >
                      Download This Version
                    </Button>
                  ) : (
                    <span className="vd-version-locked" title="Download disabled: View-only access">
                      <Lock size={14} />
                      Download disabled: View-only access
                    </span>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </Modal>
  );
};

export default VersionsModal;
