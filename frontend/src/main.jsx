import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './shared/styles/global.css';

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// Register the PWA service worker (static caching + sign-in approval push
// notifications). Registration never requests notification permission —
// that only happens from an explicit user action in Settings.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {
      // Offline/PWA support is best-effort; the app works without it.
    });
  });
}
