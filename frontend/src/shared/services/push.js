/**
 * Web Push subscription helpers for VaultDocs sign-in approvals.
 *
 * Notification permission is requested ONLY from an explicit user action
 * (the "Enable sign-in approval notifications" button in Settings), never
 * automatically on page load.
 */
import apiClient from './apiClient';

const VAPID_PUBLIC_KEY_ENDPOINT = '/devices/vapid-public-key';

/** Convert a base64url VAPID public key to a Uint8Array for the browser. */
const urlBase64ToUint8Array = (base64String) => {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
  const rawData = window.atob(base64);
  const outputArray = new Uint8Array(rawData.length);
  for (let i = 0; i < rawData.length; i += 1) {
    outputArray[i] = rawData.charCodeAt(i);
  }
  return outputArray;
};

/** True when this browser can receive Web Push at all. */
export const isPushSupported = () =>
  typeof window !== 'undefined' &&
  'serviceWorker' in navigator &&
  'PushManager' in window &&
  'Notification' in window;

/** Fetch the server's VAPID public key (null when push is not configured). */
export const getVapidPublicKey = async () => {
  const response = await apiClient.get(VAPID_PUBLIC_KEY_ENDPOINT);
  if (response && response.enabled && response.public_key) {
    return response.public_key;
  }
  return null;
};

/**
 * Subscribe this browser to sign-in approval pushes and register the
 * subscription with VaultDocs. Requests notification permission only after
 * this explicit call. Rotates keys automatically on re-subscribe.
 */
export const subscribeToPush = async (deviceName) => {
  if (!isPushSupported()) {
    throw new Error('Push notifications are not supported in this browser.');
  }

  const permission = await Notification.requestPermission();
  if (permission !== 'granted') {
    throw new Error('Notification permission denied. Enable it in your browser settings.');
  }

  const publicKey = await getVapidPublicKey();
  if (!publicKey) {
    throw new Error(
      'Push notifications are not configured on the server (VAPID keys missing).'
    );
  }

  const registration = await navigator.serviceWorker.ready;
  const subscription = await registration.pushManager.subscribe({
    userVisibleOnly: true,
    applicationServerKey: urlBase64ToUint8Array(publicKey),
  });

  const json = subscription.toJSON();
  return apiClient.post('/devices/push-subscriptions', {
    endpoint: json.endpoint,
    keys: json.keys,
    device_name: deviceName || null,
  });
};

/** List the current account's active push subscriptions. */
export const listPushSubscriptions = () => apiClient.get('/devices/push-subscriptions');

/** Remove one push subscription (stops approval pushes to that device). */
export const revokePushSubscription = (subscriptionId) =>
  apiClient.delete(`/devices/push-subscriptions/${subscriptionId}`);

/** Remove every push subscription registered to this account. */
export const revokeAllPushSubscriptions = async () => {
  const response = await listPushSubscriptions();
  const subscriptions = response?.subscriptions || [];
  await Promise.all(
    subscriptions.map((subscription) => revokePushSubscription(subscription.id))
  );
  return subscriptions.length;
};

/** Current browser Notification.permission ('default' | 'granted' | 'denied'). */
export const getNotificationPermission = () => {
  if (!isPushSupported()) return 'unsupported';
  return Notification.permission;
};

export default {
  isPushSupported,
  getVapidPublicKey,
  subscribeToPush,
  listPushSubscriptions,
  revokePushSubscription,
  revokeAllPushSubscriptions,
  getNotificationPermission,
};
