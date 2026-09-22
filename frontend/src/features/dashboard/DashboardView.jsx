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
import {
  FileText,
  FolderOpen,
  Share2,
  Upload,
  Plus,
  ArrowRight,
  ShieldAlert,
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

  const recentDocs = documents.slice(0, 5);

  const formatFileSize = (bytes) => {
    if (!bytes && bytes !== 0) return 'No File';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

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
      render: (row) => new Date(row.created_at).toLocaleDateString(),
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
        description="Here is an overview of your documents, folders, and system status."
        actions={
          <div className="vd-dashboard-actions">
            <Button
              variant="outline"
              icon={Plus}
              onClick={() => onNavigate('folders')}
            >
              New Folder
            </Button>
            <Button
              variant="primary"
              icon={Upload}
              onClick={() => onNavigate('documents')}
            >
              Manage Documents
            </Button>
          </div>
        }
      />

      {/* Stats Grid */}
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
            <Share2 size={24} />
          </div>
          <div className="vd-stat-info">
            <span className="vd-stat-value">Read-Only</span>
            <span className="vd-stat-label">Sharing Access</span>
          </div>
        </div>
      </div>

      {/* Recent Documents */}
      <Card
        title="Recent Documents"
        subtitle="Your latest created and uploaded documents"
        elevation="sm"
        headerAction={
          <Button
            variant="ghost"
            size="sm"
            icon={ArrowRight}
            onClick={() => onNavigate('documents')}
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
                onClick={() => onNavigate('documents')}
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
