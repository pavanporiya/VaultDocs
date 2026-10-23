/*
 * VaultDocs service worker.
 *
 * Responsibilities:
 *  - Lightweight static-asset caching so the PWA opens offline.
 *  - Rendering sign-in approval push notifications with
 *    "Yes, it's me" / "No, deny" actions.
 *
 * The service worker NEVER authenticates anything: notification taps only
 * open the approval page, where approval still requires a trusted-device
 * session against the API.
 */

const STATIC_CACHE = 'vaultdocs-static-v1';

self.addEventListener('install', (event) => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(STATIC_CACHE).then((cache) => cache.addAll(['/']).catch(() => undefined))
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(keys.filter((key) => key !== STATIC_CACHE).map((key) => caches.delete(key)))
      )
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const request = event.request;
  if (request.method !== 'GET') return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;
  if (url.pathname.startsWith('/v1')) return; // never cache API traffic

  event.respondWith(
    caches.match(request).then(
      (cached) =>
        cached ||
        fetch(request)
          .then((response) => {
            if (response && response.ok && request.destination === 'script') {
              const copy = response.clone();
              caches.open(STATIC_CACHE).then((cache) => cache.put(request, copy));
            }
            return response;
          })
          .catch(() => cached || caches.match('/'))
    )
  );
});

self.addEventListener('push', (event) => {
  let payload = {
    title: 'VaultDocs',
    body: 'Are you trying to sign in to VaultDocs?',
    url: '/login',
  };
  try {
    payload = { ...payload, ...event.data.json() };
  } catch {
    // Malformed payload: fall back to the generic prompt.
  }

  const isLoginApproval = payload.title === 'VaultDocs sign-in approval';
  const options = {
    body: payload.body,
    tag: payload.tag || 'vaultdocs-login',
    renotify: true,
    data: {
      url: payload.url || '/login',
      challenge_id: payload.challenge_id || null,
    },
  };

  if (isLoginApproval) {
    options.icon = '/icon.svg';
    options.badge = '/icon.svg';
    options.requireInteraction = true;
    options.actions = [
      { action: 'approve', title: "Yes, it's me" },
      { action: 'deny', title: 'No, deny' },
    ];
  }

  event.waitUntil(self.registration.showNotification(payload.title, options));
});

self.addEventListener('notificationclick', (event) => {
  event.notification.close();

  const data = event.notification.data || {};
  let target = new URL(data.url || '/login', self.registration.scope).toString();

  if (data.challenge_id) {
    if (event.action === 'approve') {
      target = new URL(
        `/approve-login?challenge=${encodeURIComponent(data.challenge_id)}&action=approve`,
        self.registration.scope
      ).toString();
    } else if (event.action === 'deny') {
      target = new URL(
        `/approve-login?challenge=${encodeURIComponent(data.challenge_id)}&action=deny`,
        self.registration.scope
      ).toString();
    }
  }

  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then((clients) => {
      for (const client of clients) {
        if ('focus' in client) {
          client.navigate(target);
          return client.focus();
        }
      }
      return self.clients.openWindow(target);
    })
  );
});
