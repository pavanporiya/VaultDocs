import React, { useState, useEffect, useRef } from 'react';
import { PageHeader, Card, Select, Button, useToast } from '../../shared/components';
import { useAuth } from '../../shared/context/AuthContext';
import apiClient from '../../shared/services/apiClient';
import { Save, RotateCcw, Cloud } from 'lucide-react';
import './Account.css';

/**
 * User preferences.
 *
 * Primary storage: backend (GET/PUT /v1/users/me/preferences — full-object
 * replacement semantics). A localStorage copy is kept explicitly as an
 * OFFLINE FALLBACK: it seeds the UI instantly on mount and receives saves
 * when the server is unreachable. Server values win when they exist.
 */
export const SETTINGS_STORAGE_KEY = 'vaultdocs.local-preferences';

const DEFAULT_SETTINGS = {
  defaultLanding: 'dashboard',
  itemsPerPage: '10',
  emailAlerts: true,
  securityAlerts: true,
};

function loadLocalSettings() {
  try {
    const raw = localStorage.getItem(SETTINGS_STORAGE_KEY);
    if (!raw) return { ...DEFAULT_SETTINGS };
    const parsed = JSON.parse(raw);
    return { ...DEFAULT_SETTINGS, ...parsed };
  } catch {
    return { ...DEFAULT_SETTINGS };
  }
}

function persistLocalSettings(settings) {
  try {
    localStorage.setItem(SETTINGS_STORAGE_KEY, JSON.stringify(settings));
    return true;
  } catch {
    return false;
  }
}

export const SettingsView = ({ onNavigate }) => {
  const { user } = useAuth();
  const toast = useToast();

  const [settings, setSettings] = useState(loadLocalSettings);
  const [hasChanges, setHasChanges] = useState(false);
  const [saving, setSaving] = useState(false);
  const [serverLoaded, setServerLoaded] = useState(false);

  const settingsRef = useRef(settings);
  settingsRef.current = settings;

  // Load server preferences once; server values win over the local seed.
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await apiClient.get('/users/me/preferences');
        if (cancelled) return;
        const serverPrefs = data?.preferences;
        if (serverPrefs && Object.keys(serverPrefs).length > 0) {
          setSettings((prev) => ({ ...prev, ...serverPrefs }));
          persistLocalSettings({ ...loadLocalSettings(), ...serverPrefs });
        }
      } catch {
        // Offline / unauthenticated: keep local values.
      } finally {
        if (!cancelled) setServerLoaded(true);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const updateSetting = (key, value) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
    setHasChanges(true);
  };

  const handleSaveSettings = async () => {
    setSaving(true);
    const current = settingsRef.current;

    // Always maintain the local fallback copy.
    persistLocalSettings(current);

    try {
      await apiClient.put('/users/me/preferences', current);
      setHasChanges(false);
      toast.success('Preferences saved to your VaultDocs account.', 'Settings Saved');
    } catch {
      // Server unreachable: the local copy is already written. Be honest
      // about what was (and was not) persisted.
      toast.warning(
        'Could not reach the server — preferences were saved in this browser only and will sync on the next successful save.',
        'Saved Locally'
      );
      setHasChanges(false);
    } finally {
      setSaving(false);
    }
  };

  const handleReset = () => {
    setSettings({ ...DEFAULT_SETTINGS });
    setHasChanges(true);
    toast.info('Settings reset to defaults. Click Save to persist.');
  };

  return (
    <div className="vd-account-view">
      <PageHeader
        title="Account Settings"
        description="Configure your VaultDocs workspace preferences. Saved to your account and synced across devices."
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
            <Button
              variant="primary"
              size="sm"
              icon={Save}
              loading={saving}
              disabled={!hasChanges}
              onClick={handleSaveSettings}
            >
              Save Settings
            </Button>
          </div>
        }
      />

      {/* Storage scope notice */}
      <Card elevation="sm" className="vd-settings-scope-card">
        <div className="vd-settings-scope">
          <Cloud size={18} className="vd-settings-scope-icon" />
          <div className="vd-settings-scope-text">
            {serverLoaded ? (
              <>
                Preferences are saved to your <strong>VaultDocs account</strong> and follow you
                across devices. A local copy is kept in this browser as an offline fallback — if a
                save cannot reach the server, it stays local and syncs on the next successful save.
              </>
            ) : (
              <>Checking your account preferences…</>
            )}
          </div>
        </div>
      </Card>

      <div className="vd-account-grid">
        <Card title="Display & Workspace Preferences" elevation="sm">
          <div className="vd-settings-section">
            <Select
              label="Default Landing Page"
              value={settings.defaultLanding}
              onChange={(e) => updateSetting('defaultLanding', e.target.value)}
              options={[
                { value: 'dashboard', label: 'Dashboard Overview' },
                { value: 'explorer', label: 'Folder Explorer' },
                { value: 'documents', label: 'All Documents' },
                { value: 'shared', label: 'Shared With Me' },
              ]}
              helperText="Which page the app opens on after sign-in"
            />

            <Select
              label="Items Per Page"
              value={settings.itemsPerPage}
              onChange={(e) => updateSetting('itemsPerPage', e.target.value)}
              options={[
                { value: '10', label: '10 items' },
                { value: '25', label: '25 items' },
                { value: '50', label: '50 items' },
                { value: '100', label: '100 items' },
              ]}
              helperText="Preferred document table page size"
            />
          </div>
        </Card>

        <Card title="Notifications & Alerts (Preference Flags)" elevation="sm">
          <div className="vd-settings-section">
            <div className="vd-settings-row">
              <div className="vd-settings-info">
                <span className="vd-settings-title">Email Notifications</span>
                <span className="vd-settings-desc">
                  Preference flag — VaultDocs does not send email notifications yet
                </span>
              </div>
              <input
                type="checkbox"
                checked={settings.emailAlerts}
                onChange={(e) => updateSetting('emailAlerts', e.target.checked)}
                aria-label="Email notifications preference"
                style={{ width: '18px', height: '18px', cursor: 'pointer' }}
              />
            </div>

            <div className="vd-settings-row">
              <div className="vd-settings-info">
                <span className="vd-settings-title">Security & Sign-in Alerts</span>
                <span className="vd-settings-desc">
                  Preference flag — no alert emails are sent by the backend
                </span>
              </div>
              <input
                type="checkbox"
                checked={settings.securityAlerts}
                onChange={(e) => updateSetting('securityAlerts', e.target.checked)}
                aria-label="Security alerts preference"
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
