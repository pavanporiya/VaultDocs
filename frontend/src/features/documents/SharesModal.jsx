import React, { useState, useEffect, useCallback } from 'react';
import { Modal, Input, Button, Table, Loader, ErrorState, useToast } from '../../shared/components';
import apiClient from '../../shared/services/apiClient';
import { UserPlus, Trash2, ShieldCheck, Mail } from 'lucide-react';
import './Modals.css';

export const SharesModal = ({ isOpen, onClose, document }) => {
  const [shares, setShares] = useState([]);
  const [recipientEmail, setRecipientEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [revokingId, setRevokingId] = useState(null);
  const [error, setError] = useState('');

  const toast = useToast();

  const fetchShares = useCallback(async () => {
    if (!document?.id) return;
    setLoading(true);
    setError('');
    try {
      const data = await apiClient.get(`/documents/${document.id}/shares`);
      setShares(data || []);
    } catch (err) {
      setError(err.message || 'Failed to load share settings.');
    } finally {
      setLoading(false);
    }
  }, [document?.id]);

  useEffect(() => {
    if (isOpen && document?.id) {
      fetchShares();
    }
  }, [isOpen, document?.id, fetchShares]);

  const handleShare = async (e) => {
    e.preventDefault();
    if (!recipientEmail.trim()) return;

    setSharing(true);
    try {
      await apiClient.post(`/documents/${document.id}/shares`, {
        user_email: recipientEmail.trim(),
      });
      toast.success(`Shared "${document.name}" with ${recipientEmail}`);
      setRecipientEmail('');
      await fetchShares();
    } catch (err) {
      toast.error(err.message || 'Failed to share document.', 'Share Error');
    } finally {
      setSharing(false);
    }
  };

  const handleRevokeShare = async (shareId) => {
    setRevokingId(shareId);
    try {
      await apiClient.delete(`/documents/${document.id}/shares/${shareId}`);
      toast.success('Share access revoked');
      await fetchShares();
    } catch (err) {
      toast.error(err.message || 'Failed to revoke access.', 'Error');
    } finally {
      setRevokingId(null);
    }
  };

  const formatDate = (isoString) => {
    if (!isoString) return 'N/A';
    return new Date(isoString).toLocaleDateString();
  };

  const columns = [
    {
      header: 'Recipient Email',
      key: 'user_email',
      render: (row) => (
        <div className="vd-doc-cell">
          <Mail size={16} />
          <span>{row.shared_with_user?.email || row.user_email || 'Registered User'}</span>
        </div>
      ),
    },
    {
      header: 'Permission',
      key: 'permission',
      render: () => (
        <div className="vd-permission-tag">
          <ShieldCheck size={14} />
          <span>Read Only</span>
        </div>
      ),
    },
    {
      header: 'Shared Date',
      key: 'created_at',
      render: (row) => formatDate(row.created_at),
    },
    {
      header: 'Action',
      key: 'action',
      align: 'right',
      render: (row) => (
        <Button
          variant="danger"
          size="sm"
          icon={Trash2}
          loading={revokingId === row.id}
          onClick={() => handleRevokeShare(row.id)}
          aria-label="Revoke share access"
        >
          Revoke
        </Button>
      ),
    },
  ];

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={`Share Document — ${document?.name || ''}`}
      size="md"
    >
      <div className="vd-share-modal-body">
        {/* Share Input Form */}
        <form onSubmit={handleShare} className="vd-share-form">
          <div className="vd-share-input-row">
            <div style={{ flex: 1 }}>
              <Input
                placeholder="Recipient registered email address..."
                type="email"
                value={recipientEmail}
                onChange={(e) => setRecipientEmail(e.target.value)}
                icon={Mail}
                required
              />
            </div>
            <Button
              variant="primary"
              type="submit"
              icon={UserPlus}
              loading={sharing}
            >
              Share
            </Button>
          </div>
          <span className="vd-share-note">
            Recipients receive read-only access to view and download this document.
          </span>
        </form>

        <div className="vd-share-divider" />

        {/* Existing Shares Table */}
        <h4 className="vd-share-section-title">Active Shares</h4>
        {loading ? (
          <div style={{ padding: '1.5rem 0', textAlign: 'center' }}>
            <Loader text="Loading share list..." />
          </div>
        ) : error ? (
          <ErrorState
            title="Could not load shares"
            description={error}
            onRetry={fetchShares}
          />
        ) : (
          <Table
            columns={columns}
            data={shares}
            emptyTitle="Not shared with anyone"
            emptyDescription="Enter an email above to share this document."
          />
        )}
      </div>
    </Modal>
  );
};

export default SharesModal;
