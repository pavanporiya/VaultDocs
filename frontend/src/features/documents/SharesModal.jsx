import React, { useState, useEffect, useCallback } from 'react';
import { Modal, Input, Button, Table, Loader, ErrorState, useToast } from '../../shared/components';
import apiClient from '../../shared/services/apiClient';
import { formatDate } from '../../shared/utils/format';
import { UserPlus, Trash2, ShieldCheck, Mail, Lock, Download, Eye } from 'lucide-react';
import './Modals.css';

/**
 * Share management modal (owner side) — the REAL document sharing workflow.
 *
 * Backend contract (verified):
 * - POST   /documents/{id}/shares            share with a registered email
 *                                            + download_allowed permission
 * - GET    /documents/{id}/shares            list shares (owner only)
 * - PATCH  /documents/{id}/shares/{share_id} change permission (download grant)
 * - DELETE /documents/{id}/shares/{share_id} revoke
 *
 * The owner explicitly chooses the recipient's permission:
 * - "View only"        -> download_allowed=false (preview only, no downloads)
 * - "View + Download"  -> download_allowed=true  (preview + file downloads)
 *
 * The chosen value is sent to the backend and persisted; no local-only state.
 * Default is deliberately the SAFER option (View only).
 *
 * Owner-only: non-owners can never open this modal. The backend enforces
 * the same rule with 403/404 regardless.
 */
export const SharesModal = ({ isOpen, onClose, document }) => {
  const [shares, setShares] = useState([]);
  const [recipientEmail, setRecipientEmail] = useState('');
  // Safe default: view-only. The owner must consciously grant downloads.
  const [sharePermission, setSharePermission] = useState('view_only');
  const [loading, setLoading] = useState(false);
  const [sharing, setSharing] = useState(false);
  const [revokingId, setRevokingId] = useState(null);
  const [updatingId, setUpdatingId] = useState(null);
  const [error, setError] = useState('');

  const toast = useToast();

  // Owner-only gate: legacy responses without flags keep owner flows working.
  const isOwner = document ? document.is_owner !== false : false;

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
        download_allowed: sharePermission === 'view_download',
      });
      toast.success(
        sharePermission === 'view_download'
          ? `Document shared with ${recipientEmail.trim()} (View + Download)`
          : `Document shared with ${recipientEmail.trim()} (View Only)`
      );
      setRecipientEmail('');
      // Reset to the safe default for the next share.
      setSharePermission('view_only');
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

  const handleChangePermission = async (share, downloadAllowed) => {
    if (share.download_allowed === downloadAllowed) return;
    setUpdatingId(share.id);
    try {
      await apiClient.patch(`/documents/${document.id}/shares/${share.id}`, {
        download_allowed: downloadAllowed,
      });
      toast.success(
        downloadAllowed
          ? 'Permission changed: View + Download'
          : 'Permission changed: View Only'
      );
      await fetchShares();
    } catch (err) {
      toast.error(err.message || 'Failed to change permission.', 'Error');
    } finally {
      setUpdatingId(null);
    }
  };

  const formatUserId = (id) => {
    if (!id) return '—';
    const str = String(id);
    return str.length > 13 ? `${str.slice(0, 8)}…${str.slice(-4)}` : str;
  };

  const columns = [
    {
      header: 'Recipient',
      key: 'shared_with_user_id',
      render: (row) => (
        <div className="vd-doc-cell">
          <Mail size={16} />
          {row.shared_with_email ? (
            <span
              className="vd-share-recipient"
              title={`Recipient user ID: ${row.shared_with_user_id}`}
            >
              {row.shared_with_email}
            </span>
          ) : (
            <span
              className="vd-share-user-id"
              title={`Recipient user ID: ${row.shared_with_user_id}`}
            >
              User {formatUserId(row.shared_with_user_id)}
            </span>
          )}
        </div>
      ),
    },
    {
      header: 'Permission',
      key: 'permission',
      render: (row) =>
        row.download_allowed === false ? (
          <div
            className="vd-permission-tag vd-permission-tag--viewonly"
            title="Preview only — downloads blocked"
          >
            <Lock size={14} />
            <span>View Only</span>
          </div>
        ) : (
          <div
            className="vd-permission-tag"
            title="Preview + file downloads allowed"
          >
            <Download size={14} />
            <span>View + Download</span>
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
        <div className="vd-share-row-actions">
          {row.download_allowed === false ? (
            <Button
              variant="ghost"
              size="sm"
              icon={Download}
              loading={updatingId === row.id}
              onClick={() => handleChangePermission(row, true)}
              aria-label={`Allow downloads for ${row.shared_with_email || 'this recipient'}`}
              title="Change permission to View + Download"
            >
              Allow Download
            </Button>
          ) : (
            <Button
              variant="ghost"
              size="sm"
              icon={Eye}
              loading={updatingId === row.id}
              onClick={() => handleChangePermission(row, false)}
              aria-label={`Restrict to view-only for ${row.shared_with_email || 'this recipient'}`}
              title="Change permission to View Only"
            >
              Make View Only
            </Button>
          )}
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
        </div>
      ),
    },
  ];

  // Owner-only guard rendered after all hooks (rules-of-hooks safe).
  if (isOpen && !isOwner) {
    return (
      <Modal isOpen={isOpen} onClose={onClose} title="Share Document" size="sm">
        <div className="vd-share-owner-guard">
          <Lock size={28} />
          <p>Only the document owner can manage sharing.</p>
        </div>
      </Modal>
    );
  }

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

          {/* Permission selector — real value sent to the backend */}
          <div
            className="vd-share-permission-group"
            role="radiogroup"
            aria-label="Recipient permission"
          >
            <button
              type="button"
              role="radio"
              aria-checked={sharePermission === 'view_only'}
              className={`vd-share-permission-option${
                sharePermission === 'view_only' ? ' is-selected' : ''
              }`}
              onClick={() => setSharePermission('view_only')}
            >
              <span className="vd-share-permission-head">
                <Lock size={15} />
                <span>View only</span>
              </span>
              <span className="vd-share-permission-desc">
                Can preview the document but cannot download, edit, delete, rename,
                move, or share.
              </span>
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={sharePermission === 'view_download'}
              className={`vd-share-permission-option${
                sharePermission === 'view_download' ? ' is-selected' : ''
              }`}
              onClick={() => setSharePermission('view_download')}
            >
              <span className="vd-share-permission-head">
                <Download size={15} />
                <span>View + Download</span>
              </span>
              <span className="vd-share-permission-desc">
                Can preview and download the document, but cannot edit, delete,
                rename, move, or share.
              </span>
            </button>
          </div>
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
