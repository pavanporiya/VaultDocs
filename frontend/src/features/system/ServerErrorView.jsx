import React from 'react';
import { Button, ErrorState } from '../../shared/components';
import { ServerOff, RefreshCw, Home } from 'lucide-react';
import './System.css';

export const ServerErrorView = ({ onNavigate, onRetry }) => {
  return (
    <div className="vd-system-view">
      <div className="vd-system-card">
        <div className="vd-system-icon-badge vd-system-icon-badge--500">
          <ServerOff size={36} />
        </div>
        <span className="vd-system-code" style={{ color: 'var(--color-danger)' }}>
          500
        </span>
        <h2 className="vd-system-title">Internal Server Error</h2>
        <p className="vd-system-desc">
          The VaultDocs server encountered an unexpected error while processing your request. Please try refreshing or return later.
        </p>

        <div className="vd-system-actions">
          {onRetry && (
            <Button
              variant="secondary"
              icon={RefreshCw}
              onClick={onRetry}
            >
              Retry Request
            </Button>
          )}
          <Button
            variant="primary"
            icon={Home}
            onClick={() => onNavigate && onNavigate('dashboard')}
          >
            Return to Dashboard
          </Button>
        </div>
      </div>
    </div>
  );
};

export default ServerErrorView;
