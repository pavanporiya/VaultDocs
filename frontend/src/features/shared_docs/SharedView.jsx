import React, { useState } from 'react';
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
import apiClient from '../../shared/services/apiClient';
import { Download, ShieldCheck, Search, FileText, Lock } from 'lucide-react';
import './SharedView.css';

export const SharedView = ({ onOpenAuthModal }) => {
  const { isAuthenticated } = useAuth();
  const [docIdInput, setDocIdInput] = useState('');
  const [sharedDocs, setSharedDocs] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const toast = useToast();

  const handleFetchSharedDoc = async (e) => {
    e.preventDefault();
    if (!docIdInput.trim()) return;

    setLoading(true);
    setError('');
    try {
      const docData = await apiClient.get(`/documents/${docIdInput.trim()}`);
      // Add to list if not already present
      setSharedDocs((prev) => {
        const exists = prev.some((d) => d.id === docData.id);
        return exists ? prev : [docData, ...prev];
      });
      toast.success(`Accessed shared document "${docData.name}"`);
    } catch (err) {
      setError(err.message || 'Shared document not found or access revoked.');
      toast.error(err.message || 'Access denied.', 'Shared Access');
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadSharedFile = async (doc) => {
    try {
      const token = localStorage.getItem('vaultdocs_token');
      const response = await fetch(`/v1/documents/${doc.id}/download`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });

      if (!response.ok) {
        throw new Error('Could not download shared file.');
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
      toast.error(err.message || 'Download failed.', 'Error');
    }
  };

  const columns = [
    {
      header: 'Document Name',
      key: 'name',
      render: (row) => (
        <div className="vd-shared-doc-cell">
          <FileText size={18} className="vd-shared-doc-icon" />
          <span className="vd-shared-doc-name">{row.name}</span>
        </div>
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
      header: 'Original File',
      key: 'original_filename',
      render: (row) => row.original_filename || '—',
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
          disabled={!row.file_path}
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
        description="Access and download documents shared with your registered email in read-only mode."
      />

      <Card
        title="Access Shared Document by ID"
        subtitle="Owners can share document UUIDs with you to grant instant read-only access."
        elevation="sm"
      >
        <form onSubmit={handleFetchSharedDoc} className="vd-shared-lookup-form">
          <Input
            placeholder="Paste Shared Document UUID (e.g. 4683886e-ca4c-4bd5-a271-08ba9e720112)..."
            value={docIdInput}
            onChange={(e) => setDocIdInput(e.target.value)}
            icon={Search}
            required
          />
          <Button variant="primary" type="submit" icon={ShieldCheck} loading={loading}>
            Access Document
          </Button>
        </form>
      </Card>

      <Card title="Shared Documents Session List" elevation="sm" style={{ marginTop: '1.5rem' }}>
        {error ? (
          <ErrorState
            title="Shared document lookup failed"
            description={error}
          />
        ) : (
          <Table
            columns={columns}
            data={sharedDocs}
            emptyTitle="No shared documents loaded"
            emptyDescription="Paste a shared document UUID above or ask a teammate to share a document with your email."
          />
        )}
      </Card>
    </div>
  );
};

export default SharedView;
