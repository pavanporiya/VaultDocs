/**
 * Sign-in security settings: Web Push approval notifications and trusted
 * device / notification-subscription management.
 *
 * Notification permission is requested only from the explicit enable button
 * (never on mount). Revoking a device forces approval on its next sign-in.
 */
import React, { useState, useEffect, useCallback } from 'react';
import { Card, Button, useToast } from '../../shared/components';
import apiClient from '../../shared/services/apiClient';
import {
  isPushSupported,
  getNotificationPermission,
  subscribeToPush,
  listPushSubscriptions,
  revokeAllPushSubscriptions,
} from '../../shared/services/push';
import { Smartphone, Bell, BellOff, Trash2, RefreshCw, ShieldAlert } from 'lucide-react';

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
  const [subscriptions, setSubscriptions] = useState([]);
  const [permission, setPermission] = useState(() => getNotificationPermission());
  const [loading, setLoading] = useState(true);
  const [busyKey, setBusyKey] = useState(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const [deviceRes, subscriptionRes] = await Promise.all([
        apiClient.get('/devices'),
        listPushSubscriptions(),
      ]);
      setDevices(deviceRes?.devices || []);
      setSubscriptions(subscriptionRes?.subscriptions || []);
    } catch {
      // Unauthenticated/offhandled upstream; leave lists empty.
    } finally {
      setLoading(false);
      setPermission(getNotificationPermission());
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const handleEnablePush = async () => {
    setBusyKey('enable-push');
    try {
      await subscribeToPush(navigator.userAgent.slice(0, 60));
      setPermission(getNotificationPermission());
      await refresh();
      toast.success(
        'This device will now receive "Are you trying to sign in?" approvals.',
        'Notifications Enabled'
      );
    } catch (err) {
      toast.error(
        err?.message || 'Could not enable notifications.',
        'Setup Failed'
      );
    } finally {
      setBusyKey(null);
    }
  };

  const handleDisablePush = async () => {
    setBusyKey('disable-push');
    try {
      const count = await revokeAllPushSubscriptions();
      await refresh();
      toast.info(
        count > 0
          ? `Removed ${count} notification subscription(s).`
          : 'No notification subscriptions to remove.',
        'Notifications Disabled'
      );
    } catch (err) {
      toast.error(err?.message || 'Could not disable notifications.', 'Error');
    } finally {
      setBusyKey(null);
    }
  };

  const handleRevokeDevice = async (deviceId) => {
    setBusyKey(`device-${deviceId}`);
    try {
      await apiClient.delete(`/devices/${deviceId}`);
      await refresh();
      toast.info('Device revoked. Its next sign-in will require approval.', 'Device Revoked');
    } catch (err) {
      toast.error(err?.message || 'Could not revoke device.', 'Error');
    } finally {
      setBusyKey(null);
    }
  };

  const handleRevokeAll = async () => {
    setBusyKey('revoke-all');
    try {
      await Promise.all(
        devices.map((device) => apiClient.delete(`/devices/${device.id}`))
      );
      await revokeAllPushSubscriptions();
      await refresh();
      toast.info(
        'All trusted devices and notification subscriptions were revoked.',
        'Security Reset'
      );
    } catch (err) {
      toast.error(err?.message || 'Could not revoke all devices.', 'Error');
    } finally {
      setBusyKey(null);
    }
  };

  const handleRevokeSubscription = async (subscriptionId) => {
    setBusyKey(`sub-${subscriptionId}`);
    try {
      await apiClient.delete(`/devices/push-subscriptions/${subscriptionId}`);
      await refresh();
      toast.info('Notification subscription removed.', 'Removed');
    } catch (err) {
      toast.error(err?.message || 'Could not remove subscription.', 'Error');
    } finally {
      setBusyKey(null);
    }
  };

  const pushSupported = isPushSupported();

  return (
    <>
      <Card title="Sign-In Approval Notifications" elevation="sm">
        <div className="vd-settings-section">
          <div className="vd-settings-row">
            <div className="vd-settings-info">
              <span className="vd-settings-title">Phone Approval (Web Push)</span>
              <span className="vd-settings-desc">
                {!pushSupported
                  ? 'Push notifications are not supported in this browser. Install the VaultDocs PWA on your phone (HTTPS required) to approve sign-ins.'
                  : permission === 'granted'
                    ? 'Enabled. New sign-ins on other devices will notify this phone: "Are you trying to sign in to VaultDocs?"'
                    : permission === 'denied'
                      ? 'Notifications are blocked for this site. Allow them in your browser settings, then try again.'
                      : 'Receive a push notification to approve new-device sign-ins. Permission is requested only when you click Enable.'}
              </span>
            </div>
            {permission === 'granted' ? (
              <Button
                variant="outline"
                size="sm"
                icon={BellOff}
                loading={busyKey === 'disable-push'}
                onClick={handleDisablePush}
              >
                Disable
              </Button>
            ) : (
              <Button
                variant="primary"
                size="sm"
                icon={Bell}
                disabled={!pushSupported || permission === 'denied'}
                loading={busyKey === 'enable-push'}
                onClick={handleEnablePush}
              >
                Enable Notifications
              </Button>
            )}
          </div>

          {subscriptions.length > 0 && (
            <div className="vd-settings-row">
              <div className="vd-settings-info">
                <span className="vd-settings-title">Registered Devices</span>
                <span className="vd-settings-desc">
                  {subscriptions.map((subscription) => `${subscription.device_name || 'Browser'} (${new URL(subscription.endpoint).host})`).join(', ')}
                </span>
              </div>
            </div>
          )}

          {subscriptions.map((subscription) => (
            <div className="vd-settings-row" key={subscription.id}>
              <div className="vd-settings-info">
                <span className="vd-settings-title">
                  <Smartphone size={14} style={{ display: 'inline', marginRight: 6 }} />
                  {subscription.device_name || 'Browser'}
                </span>
                <span className="vd-settings-desc">
                  Added {formatDate(subscription.created_at)} ·{' '}
                  {new URL(subscription.endpoint).host}
                </span>
              </div>
              <Button
                variant="ghost"
                size="sm"
                icon={Trash2}
                loading={busyKey === `sub-${subscription.id}`}
                onClick={() => handleRevokeSubscription(subscription.id)}
              >
                Remove
              </Button>
            </div>
          ))}
        </div>
      </Card>

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
                  Tick &ldquo;Remember this device for 30 days&rdquo; at sign-in (after approving
                  from your phone) to list a device here.
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
                  Revoke every trusted device and notification subscription. All devices will
                  need phone approval on their next sign-in.
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
    </>
  );
};

export default SecuritySettings;
