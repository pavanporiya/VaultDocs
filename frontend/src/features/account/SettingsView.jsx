import React, { useState } from 'react';
import { PageHeader, Card, Select, Button, useToast } from '../../shared/components';
import { useAuth } from '../../shared/context/AuthContext';
import { Save, RotateCcw } from 'lucide-react';
import './Account.css';

export const SettingsView = ({ onNavigate }) => {
  const { user } = useAuth();
  const toast = useToast();

  // Settings State (stored in component state / localStorage)
  const [defaultLanding, setDefaultLanding] = useState('dashboard');
  const [itemsPerPage, setItemsPerPage] = useState('10');
  const [emailAlerts, setEmailAlerts] = useState(true);
  const [securityAlerts, setSecurityAlerts] = useState(true);
  const [saving, setSaving] = useState(false);

  const handleSaveSettings = () => {
    setSaving(true);
    setTimeout(() => {
      setSaving(false);
      toast.success('Account preferences saved successfully!', 'Settings Updated');
    }, 400);
  };

  const handleReset = () => {
    setDefaultLanding('dashboard');
    setItemsPerPage('10');
    setEmailAlerts(true);
    setSecurityAlerts(true);
    toast.info('Settings reset to defaults.');
  };

  return (
    <div className="vd-account-view">
      <PageHeader
        title="Account Settings"
        description="Configure your interface preferences, notification options, and system behavior."
        breadcrumbs={[
          { label: 'Dashboard', onClick: () => onNavigate && onNavigate('dashboard') },
          { label: 'Profile', onClick: () => onNavigate && onNavigate('profile') },
          { label: 'Settings' },
        ]}
        actions={
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <Button variant="ghost" size="sm" icon={RotateCcw} onClick={handleReset}>
              Reset
            </Button>
            <Button variant="primary" size="sm" icon={Save} loading={saving} onClick={handleSaveSettings}>
              Save Settings
            </Button>
          </div>
        }
      />

      <div className="vd-account-grid">
        <Card title="Display & Workspace Preferences" elevation="sm">
          <div className="vd-settings-section">
            <Select
              label="Default Landing Page"
              value={defaultLanding}
              onChange={(e) => setDefaultLanding(e.target.value)}
              options={[
                { value: 'dashboard', label: 'Dashboard Overview' },
                { value: 'explorer', label: 'Folder Explorer' },
                { value: 'documents', label: 'All Documents' },
                { value: 'sharing', label: 'Shared With Me' },
              ]}
              helperText="Choose which page opens automatically upon log in"
            />

            <Select
              label="Items Per Page"
              value={itemsPerPage}
              onChange={(e) => setItemsPerPage(e.target.value)}
              options={[
                { value: '10', label: '10 items' },
                { value: '25', label: '25 items' },
                { value: '50', label: '50 items' },
                { value: '100', label: '100 items' },
              ]}
              helperText="Default document table pagination size"
            />
          </div>
        </Card>

        <Card title="Notifications & Alerts" elevation="sm">
          <div className="vd-settings-section">
            <div className="vd-settings-row">
              <div className="vd-settings-info">
                <span className="vd-settings-title">Email Notifications</span>
                <span className="vd-settings-desc">Receive email summaries when documents are shared with you</span>
              </div>
              <input
                type="checkbox"
                checked={emailAlerts}
                onChange={(e) => setEmailAlerts(e.target.checked)}
                style={{ width: '18px', height: '18px', cursor: 'pointer' }}
              />
            </div>

            <div className="vd-settings-row">
              <div className="vd-settings-info">
                <span className="vd-settings-title">Security & Sign-in Alerts</span>
                <span className="vd-settings-desc">Get notified of new logins or authorization changes</span>
              </div>
              <input
                type="checkbox"
                checked={securityAlerts}
                onChange={(e) => setSecurityAlerts(e.target.checked)}
                style={{ width: '18px', height: '18px', cursor: 'pointer' }}
              />
            </div>
          </div>
        </Card>
      </div>

      <Card title="Account Security Information" elevation="sm">
        <div className="vd-settings-section">
          <div className="vd-settings-row">
            <div className="vd-settings-info">
              <span className="vd-settings-title">Authenticated Email</span>
              <span className="vd-settings-desc">{user ? user.email : 'Not signed in'}</span>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={() => onNavigate && onNavigate('profile')}
            >
              View Profile
            </Button>
          </div>
        </div>
      </Card>
    </div>
  );
};

export default SettingsView;
