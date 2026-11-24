/**
 * Sign-in security settings: trusted device management.
 *
 * Lists the server-verified trusted devices behind "Remember this device
 * for 30 days" (secure HttpOnly cookie + hashed token). Revoking a device
 * forces the email OTP on its next sign-in.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Card, Button, useToast } from '../../shared/components';
import apiClient from '../../shared/services/apiClient';
import { Trash2, RefreshCw, ShieldAlert } from 'lucide-react';

const formatDate = (value) => {
  if (!value) return '—';
  try {
    return new Date(value).toLocaleString();
  } catch {
    return '—';
  }
};

export const SecuritySettings = () => {
  const toast = useToast();

  const [devices, setDevices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busyKey, setBusyKey] = useState(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const deviceRes = await apiClient.get('/devices');
      setDevices(deviceRes?.devices || []);
    } catch {
      // Unauthenticated/handled upstream; leave the list empty.
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleRevokeDevice = async (deviceId) => {
    setBusyKey(`device-${deviceId}`);
    try {
      await apiClient.delete(`/devices/${deviceId}`);
      await refresh();
      toast.info('Device revoked. Its next sign-in will require the email code.', 'Device Revoked');
    } catch (err) {
      toast.error(err?.message || 'Could not revoke device.', 'Error');
    } finally {
      setBusyKey(null);
    }
  };

  const handleRevokeAll = async () => {
    setBusyKey('revoke-all');
    try {
      await Promise.all(devices.map((device) => apiClient.delete(`/devices/${device.id}`)));
      await refresh();
      toast.info('All trusted devices were revoked.', 'Security Reset');
    } catch (err) {
      toast.error(err?.message || 'Could not revoke all devices.', 'Error');
    } finally {
      setBusyKey(null);
    }
  };

  return (
    <Card title="Trusted Devices (Remember for 30 Days)" elevation="sm">
      <div className="vd-settings-section">
        {loading && devices.length === 0 && (
          <span className="vd-settings-desc">Loading trusted devices…</span>
        )}

        {!loading && devices.length === 0 && (
          <div className="vd-settings-row">
            <div className="vd-settings-info">
              <span className="vd-settings-title">No trusted devices</span>
              <span className="vd-settings-desc">
                Tick &ldquo;Remember this device for 30 days&rdquo; when you enter your email
                sign-in code to list a device here.
              </span>
            </div>
          </div>
        )}

        {devices.map((device) => {
          const expired = new Date(device.expires_at) <= new Date();
          return (
            <div className="vd-settings-row" key={device.id}>
              <div className="vd-settings-info">
                <span className="vd-settings-title">
                  {device.device_name || 'Unnamed device'}
                  {device.is_current && !device.revoked_at && (
                    <span
                      style={{
                        marginLeft: 8,
                        fontSize: '0.6875rem',
                        color: 'var(--color-success, #22c55e)',
                      }}
                    >
                      (this device)
                    </span>
                  )}
                  {device.revoked_at && (
                    <span
                      style={{
                        marginLeft: 8,
                        fontSize: '0.6875rem',
                        color: 'var(--color-text-muted, #64748b)',
                      }}
                    >
                      (revoked)
                    </span>
                  )}
                  {!device.revoked_at && expired && (
                    <span
                      style={{
                        marginLeft: 8,
                        fontSize: '0.6875rem',
                        color: 'var(--color-warning, #f59e0b)',
                      }}
                    >
                      (expired)
                    </span>
                  )}
                </span>
                <span className="vd-settings-desc">
                  Added {formatDate(device.created_at)} · Trust{' '}
                  {device.revoked_at
                    ? 'revoked'
                    : expired
                      ? 'expired'
                      : `until ${formatDate(device.expires_at)}`}
                  {device.user_agent ? ` · ${device.user_agent}` : ''}
                </span>
              </div>
              {!device.revoked_at && (
                <Button
                  variant="ghost"
                  size="sm"
                  icon={Trash2}
                  loading={busyKey === `device-${device.id}`}
                  onClick={() => handleRevokeDevice(device.id)}
                >
                  Revoke
                </Button>
              )}
            </div>
          );
        })}

        {devices.some((device) => !device.revoked_at) && (
          <div className="vd-settings-row">
            <div className="vd-settings-info">
              <span className="vd-settings-title">
                <ShieldAlert size={14} style={{ display: 'inline', marginRight: 6 }} />
                Emergency reset
              </span>
              <span className="vd-settings-desc">
                Revoke every trusted device. All devices will need the email sign-in code on
                their next sign-in.
              </span>
            </div>
            <Button
              variant="outline"
              size="sm"
              icon={RefreshCw}
              loading={busyKey === 'revoke-all'}
              onClick={handleRevokeAll}
            >
              Revoke All
            </Button>
          </div>
        )}
      </div>
    </Card>
  );
};

export default SecuritySettings;
