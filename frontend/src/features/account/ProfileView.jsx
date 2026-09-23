import React, { useState } from 'react';
import { PageHeader, Card, Button, Input, Loader, ErrorState, useToast } from '../../shared/components';
import { useAuth } from '../../shared/context/AuthContext';
import apiClient from '../../shared/services/apiClient';
import { ShieldCheck, RefreshCw, LogOut, Settings, Edit2, X } from 'lucide-react';
import './Account.css';

export const ProfileView = ({ onNavigate }) => {
  const { user, isLoading, refreshUser, logout } = useAuth();
  const toast = useToast();
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  // Profile edit state (PATCH /v1/auth/me)
  const [isEditing, setIsEditing] = useState(false);
  const [editFullName, setEditFullName] = useState('');
  const [savingName, setSavingName] = useState(false);
  const [nameError, setNameError] = useState('');

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

  const openEdit = () => {
    setEditFullName(user?.full_name || '');
    setNameError('');
    setIsEditing(true);
  };

  const cancelEdit = () => {
    setIsEditing(false);
    setEditFullName('');
    setNameError('');
  };

  const handleSaveName = async (e) => {
    e.preventDefault();
    if (!editFullName.trim() || editFullName.trim().length < 2) {
      setNameError('Full name must be at least 2 characters.');
      return;
    }

    setSavingName(true);
    setNameError('');
    try {
      await apiClient.patch('/auth/me', { full_name: editFullName.trim() });
      await refreshUser(); // reload /auth/me into the auth context
      toast.success('Profile updated.', 'Saved');
      setIsEditing(false);
    } catch (err) {
      const message = err?.message || 'Failed to update profile.';
      setNameError(message);
      toast.error(message, 'Update Failed');
    } finally {
      setSavingName(false);
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
          {isEditing ? (
            <form onSubmit={handleSaveName} className="vd-profile-edit-form">
              <Input
                label="Full Name"
                value={editFullName}
                onChange={(e) => setEditFullName(e.target.value)}
                error={nameError || undefined}
                required
                autoFocus
                disabled={savingName}
              />
              <div className="vd-profile-edit-actions">
                <Button
                  variant="secondary"
                  size="sm"
                  icon={X}
                  type="button"
                  onClick={cancelEdit}
                  disabled={savingName}
                >
                  Cancel
                </Button>
                <Button variant="primary" size="sm" type="submit" loading={savingName}>
                  Save Changes
                </Button>
              </div>
            </form>
          ) : (
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
              <div className="vd-info-row" style={{ marginTop: '0.5rem' }}>
                <Button variant="outline" size="sm" icon={Edit2} onClick={openEdit}>
                  Edit Full Name
                </Button>
              </div>
            </div>
          )}
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
