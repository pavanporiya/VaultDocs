import React from 'react';
import { Button } from '../../shared/components';
import { FileQuestion, Home, ArrowLeft } from 'lucide-react';
import './System.css';

export const NotFoundView = ({ onNavigate }) => {
  return (
    <div className="vd-system-view">
      <div className="vd-system-card">
        <div className="vd-system-icon-badge vd-system-icon-badge--404">
          <FileQuestion size={36} />
        </div>
        <span className="vd-system-code" style={{ color: 'var(--color-primary)' }}>
          404
        </span>
        <h2 className="vd-system-title">Page Not Found</h2>
        <p className="vd-system-desc">
          The page or document route you are looking for does not exist, has been removed, or is temporarily unavailable.
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

export default NotFoundView;
