import React, { useState, useEffect } from 'react';
import { Button } from '../../shared/components';
import { WifiOff, RefreshCw, CheckCircle2 } from 'lucide-react';
import './System.css';

export const OfflineView = ({ onNavigate }) => {
  const [isOnline, setIsOnline] = useState(navigator.onLine);
  const [checking, setChecking] = useState(false);

  useEffect(() => {
    const handleOnline = () => setIsOnline(true);
    const handleOffline = () => setIsOnline(false);

    window.addEventListener('online', handleOnline);
    window.addEventListener('offline', handleOffline);

    return () => {
      window.removeEventListener('online', handleOnline);
      window.removeEventListener('offline', handleOffline);
    };
  }, []);

  const handleCheckConnection = () => {
    setChecking(true);
    setTimeout(() => {
      setIsOnline(navigator.onLine);
      setChecking(false);
    }, 600);
  };

  return (
    <div className="vd-system-view">
      <div className="vd-system-card">
        <div className={`vd-system-icon-badge ${isOnline ? 'vd-system-icon-badge--404' : 'vd-system-icon-badge--offline'}`}>
          {isOnline ? <CheckCircle2 size={36} color="var(--color-success)" /> : <WifiOff size={36} />}
        </div>

        <h2 className="vd-system-title">
          {isOnline ? 'Connection Restored' : 'You Are Currently Offline'}
        </h2>
        <p className="vd-system-desc">
          {isOnline
            ? 'Your internet connection is back active. You can resume working now.'
            : 'VaultDocs cannot connect to the network. Please check your internet connection or Wi-Fi.'}
        </p>

        <div className="vd-system-actions">
          <Button
            variant="primary"
            icon={RefreshCw}
            loading={checking}
            onClick={handleCheckConnection}
          >
            {isOnline ? 'Refresh Page' : 'Check Connection'}
          </Button>

          {isOnline && (
            <Button
              variant="outline"
              onClick={() => onNavigate && onNavigate('dashboard')}
            >
              Go to Dashboard
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};

export default OfflineView;
