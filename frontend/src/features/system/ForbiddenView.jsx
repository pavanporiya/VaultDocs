import React from 'react';
import { Button } from '../../shared/components';
import { Lock, Home, ArrowLeft } from 'lucide-react';
import './System.css';

export const ForbiddenView = ({ onNavigate }) => {
  return (
    <div className="vd-system-view">
      <div className="vd-system-card">
        <div className="vd-system-icon-badge vd-system-icon-badge--403">
          <Lock size={36} />
        </div>
        <span className="vd-system-code" style={{ color: 'var(--color-danger)' }}>
          403
        </span>
        <h2 className="vd-system-title">Access Denied</h2>
        <p className="vd-system-desc">
          You do not have permission to view or manage this document or workspace section. Contact the owner if you believe this is an error.
        </p>

        <div className="vd-system-actions">
          <Button
            variant="outline"
            icon={ArrowLeft}
            onClick={() => window.history.back()}
          >
            Go Back
          </Button>
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

export default ForbiddenView;
