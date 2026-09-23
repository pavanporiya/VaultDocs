import React, { useState, useEffect, useCallback } from 'react';
import {
  PageHeader,
  Card,
  Table,
  Button,
  Loader,
  EmptyState,
  ErrorState,
} from '../../shared/components';
import { useAuth } from '../../shared/context/AuthContext';
import apiClient from '../../shared/services/apiClient';
import { formatFileSize, formatDate } from '../../shared/utils/format';
import {
  FileText,
  FolderOpen,
  HardDrive,
  Upload,
  Plus,
  ArrowRight,
  ShieldAlert,
  Share2,
  Search,
} from 'lucide-react';
import './DashboardView.css';

export const DashboardView = ({ onNavigate, onOpenAuthModal }) => {
  const { user, isAuthenticated } = useAuth();
  const [documents, setDocuments] = useState([]);
  const [folders, setFolders] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const loadDashboardData = useCallback(async () => {
    if (!isAuthenticated) return;
    setLoading(true);
    setError('');
    try {
      const [docsData, foldersData] = await Promise.all([
        apiClient.get('/documents'),
        apiClient.get('/folders'),
      ]);
      setDocuments(docsData || []);
      setFolders(foldersData || []);
    } catch (err) {
      setError(err.message || 'Failed to load dashboard data.');
    } finally {
      setLoading(false);
    }
  }, [isAuthenticated]);

  useEffect(() => {
    loadDashboardData();
  }, [loadDashboardData]);

  // Backend lists documents oldest-first; "Recent" shows the newest entries.
  const recentDocs = [...documents]
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
    .slice(0, 5);

  // Real derived metrics from actual backend data.
  const totalStorageBytes = documents.reduce(
    (sum, doc) => sum + (typeof doc.file_size === 'number' ? doc.file_size : 0),
    0
  );
  const uploadedCount = documents.filter(
    (doc) => doc.original_filename || typeof doc.file_size === 'number'
  ).length;

  const columns = [
    {
      header: 'Document Name',
      key: 'name',
      render: (row) => (
        <div className="vd-dashboard-doc-cell">
          <FileText size={18} className="vd-dashboard-doc-icon" />
          <span className="vd-dashboard-doc-name">{row.name}</span>
        </div>
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

  if (!isAuthenticated) {
    return (
      <div className="vd-dashboard">
        <PageHeader
          title="VaultDocs Overview"
          description="Secure, role-based, version-controlled document management system."
        />

        <Card elevation="sm" className="vd-guest-card">
          <div className="vd-guest-content">
            <div className="vd-guest-icon">
              <ShieldAlert size={48} />
            </div>
            <h3>Authentication Required</h3>
            <p>
              Please log in or register an account to access your documents, manage folders, and share files securely.
            </p>
            <div className="vd-guest-actions">
              <Button variant="primary" onClick={() => onOpenAuthModal('login')}>
                Sign In
              </Button>
              <Button variant="outline" onClick={() => onOpenAuthModal('register')}>
                Register Account
              </Button>
            </div>
          </div>
        </Card>
      </div>
    );
  }

  return (
    <div className="vd-dashboard">
      <PageHeader
        title={`Welcome back, ${user?.full_name || 'User'}`}
        description="Here is an overview of your documents, folders, and storage."
        actions={
          <div className="vd-dashboard-actions">
            <Button
              variant="outline"
              icon={Plus}
              onClick={() => onNavigate('/explorer')}
            >
              New Folder
            </Button>
            <Button
              variant="primary"
              icon={Upload}
              onClick={() => onNavigate('/documents')}
            >
              Manage Documents
            </Button>
          </div>
        }
      />

      {/* Quick navigation */}
      <div className="vd-dashboard-quicknav">
        <Button variant="outline" size="sm" icon={FolderOpen} onClick={() => onNavigate('/explorer')}>
          Explorer
        </Button>
        <Button variant="outline" size="sm" icon={FileText} onClick={() => onNavigate('/documents')}>
          All Documents
        </Button>
        <Button variant="outline" size="sm" icon={Search} onClick={() => onNavigate('/documents')}>
          Search
        </Button>
        <Button variant="outline" size="sm" icon={Share2} onClick={() => onNavigate('/shared')}>
          Shared With Me
        </Button>
      </div>

      {/* Stats Grid — all values derived from real backend data */}
      <div className="vd-stats-grid">
        <div className="vd-stat-card">
          <div className="vd-stat-icon vd-stat-icon--blue">
            <FileText size={24} />
          </div>
          <div className="vd-stat-info">
            <span className="vd-stat-value">{documents.length}</span>
            <span className="vd-stat-label">Total Documents</span>
          </div>
        </div>

        <div className="vd-stat-card">
          <div className="vd-stat-icon vd-stat-icon--green">
            <FolderOpen size={24} />
          </div>
          <div className="vd-stat-info">
            <span className="vd-stat-value">{folders.length}</span>
            <span className="vd-stat-label">Folders</span>
          </div>
        </div>

        <div className="vd-stat-card">
          <div className="vd-stat-icon vd-stat-icon--purple">
            <HardDrive size={24} />
          </div>
          <div className="vd-stat-info">
            <span className="vd-stat-value">{formatFileSize(totalStorageBytes)}</span>
            <span className="vd-stat-label">
              Storage Used ({uploadedCount} file{uploadedCount === 1 ? '' : 's'})
            </span>
          </div>
        </div>
      </div>

      {/* Recent Documents */}
      <Card
        title="Recent Documents"
        subtitle="Your five most recently created documents"
        elevation="sm"
        headerAction={
          <Button
            variant="ghost"
            size="sm"
            icon={ArrowRight}
            onClick={() => onNavigate('/documents')}
          >
            View All
          </Button>
        }
      >
        {loading ? (
          <div style={{ padding: '2rem 0', textAlign: 'center' }}>
            <Loader text="Fetching recent documents..." />
          </div>
        ) : error ? (
          <ErrorState
            title="Unable to load documents"
            description={error}
            onRetry={loadDashboardData}
          />
        ) : recentDocs.length === 0 ? (
          <EmptyState
            title="No documents yet"
            description="Create your first document to start organizing your files."
            action={
              <Button
                variant="primary"
                size="sm"
                icon={Plus}
                onClick={() => onNavigate('/documents')}
              >
                Create Document
              </Button>
            }
          />
        ) : (
          <Table columns={columns} data={recentDocs} />
        )}
      </Card>
    </div>
  );
};

export default DashboardView;
