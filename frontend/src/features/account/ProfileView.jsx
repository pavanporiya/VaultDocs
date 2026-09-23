import React, { useState } from 'react';
import { PageHeader, Card, Button, Loader, ErrorState, useToast } from '../../shared/components';
import { useAuth } from '../../shared/context/AuthContext';
import { User, ShieldCheck, Mail, Key, RefreshCw, LogOut, Settings } from 'lucide-react';
import './Account.css';

export const ProfileView = ({ onNavigate }) => {
  const { user, isLoading, refreshUser, logout } = useAuth();
  const toast = useToast();
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  const handleRefresh = async () => {
    setRefreshing(true);
    setError(null);
    try {
      await refreshUser();
      toast.success('Profile refreshed', 'Success');
    } catch (err) {
      setError(err?.message || 'Failed to refresh profile data');
      toast.error(err?.message || 'Failed to refresh profile', 'Error');
    } finally {
      setRefreshing(false);
    }
  };

  if (isLoading) {
    return <Loader variant="component" size="lg" text="Loading profile information..." />;
  }

  if (error) {
    return (
      <div className="vd-account-view">
        <PageHeader title="User Profile" description="Manage your account details and security settings" />
        <ErrorState
          title="Unable to load profile"
          description={error}
          onRetry={handleRefresh}
          retryLabel="Retry Loading Profile"
        />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="vd-account-view">
        <PageHeader title="User Profile" description="Manage your account details and security settings" />
        <Card title="Not Signed In" elevation="sm">
          <p style={{ marginBottom: '1rem', color: 'var(--color-text-muted)' }}>
            You are currently browsing as a guest. Please sign in to view your profile details.
          </p>
          <Button variant="primary" onClick={() => onNavigate && onNavigate('login')}>
            Sign In Now
          </Button>
        </Card>
      </div>
    );
  }

  // Generate initials for avatar
  const initials = user.full_name
    ? user.full_name
        .split(' ')
        .map((n) => n[0])
        .join('')
        .toUpperCase()
        .slice(0, 2)
    : user.email?.[0]?.toUpperCase() || 'U';

  return (
    <div className="vd-account-view">
      <PageHeader
        title="User Profile"
        description="Manage your VaultDocs profile, authentication information, and account details."
        breadcrumbs={[
          { label: 'Dashboard', onClick: () => onNavigate && onNavigate('dashboard') },
          { label: 'Profile' },
        ]}
        actions={
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <Button
              variant="outline"
              size="sm"
              icon={RefreshCw}
              loading={refreshing}
              onClick={handleRefresh}
            >
              Refresh
            </Button>
            <Button
              variant="primary"
              size="sm"
              icon={Settings}
              onClick={() => onNavigate && onNavigate('settings')}
            >
              Settings
            </Button>
          </div>
        }
      />

      <div className="vd-profile-header-card">
        <div className="vd-profile-avatar">{initials}</div>
        <div className="vd-profile-meta">
          <h2 className="vd-profile-name">{user.full_name || 'VaultDocs User'}</h2>
          <span className="vd-profile-email">{user.email}</span>
          <div className="vd-profile-badges">
            <span className="vd-badge vd-badge--success">
              <ShieldCheck size={12} style={{ marginRight: '4px' }} /> Active Account
            </span>
            {user.is_superuser && (
              <span className="vd-badge vd-badge--primary">Superuser</span>
            )}
          </div>
        </div>
      </div>

      <div className="vd-account-grid">
        <Card title="Account Overview" elevation="sm">
          <div className="vd-profile-info-list">
            <div className="vd-info-row">
              <span className="vd-info-label">Full Name</span>
              <span className="vd-info-value">{user.full_name || 'N/A'}</span>
            </div>
            <div className="vd-info-row">
              <span className="vd-info-label">Email Address</span>
              <span className="vd-info-value">{user.email}</span>
            </div>
            <div className="vd-info-row">
              <span className="vd-info-label">User ID</span>
              <span className="vd-info-value" style={{ fontFamily: 'var(--font-family-mono)', fontSize: '0.8rem' }}>
                {user.id || 'Local Token'}
              </span>
            </div>
            <div className="vd-info-row">
              <span className="vd-info-label">Account Status</span>
              <span className="vd-info-value" style={{ color: 'var(--color-success)' }}>
                {user.is_active !== false ? 'Active' : 'Disabled'}
              </span>
            </div>
          </div>
        </Card>

        <Card title="Security & Authentication" elevation="sm">
          <div className="vd-profile-info-list">
            <div className="vd-info-row">
              <span className="vd-info-label">Auth Token Type</span>
              <span className="vd-info-value">Bearer (JWT)</span>
            </div>
            <div className="vd-info-row">
              <span className="vd-info-label">Session Storage</span>
              <span className="vd-info-value">localStorage</span>
            </div>
            <div className="vd-info-row">
              <span className="vd-info-label">Role Access</span>
              <span className="vd-info-value">{user.is_superuser ? 'Administrator' : 'Standard User'}</span>
            </div>
            <div className="vd-info-row" style={{ marginTop: '0.5rem' }}>
              <Button
                variant="danger"
                size="sm"
                icon={LogOut}
                onClick={() => {
                  logout();
                  toast.info('You have logged out.');
                  if (onNavigate) onNavigate('dashboard');
                }}
              >
                Sign Out
              </Button>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
};

export default ProfileView;
