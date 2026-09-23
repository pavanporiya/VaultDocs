import React from 'react';
import { Button } from '../../shared/components';
import { ShieldAlert, LogIn, Home } from 'lucide-react';
import './System.css';

export const UnauthorizedView = ({ onNavigate, onOpenAuthModal }) => {
  const handleSignIn = () => {
    if (onOpenAuthModal) {
      onOpenAuthModal('login');
    } else if (onNavigate) {
      onNavigate('login');
    }
  };

  return (
    <div className="vd-system-view">
      <div className="vd-system-card">
        <div className="vd-system-icon-badge vd-system-icon-badge--401">
          <ShieldAlert size={36} />
        </div>
        <span className="vd-system-code" style={{ color: 'var(--color-warning)' }}>
          401
        </span>
        <h2 className="vd-system-title">Authentication Required</h2>
        <p className="vd-system-desc">
          You must be logged in to access this page or resource. Please sign in to continue accessing your VaultDocs workspace.
        </p>

        <div className="vd-system-actions">
          <Button
            variant="outline"
            icon={Home}
            onClick={() => onNavigate && onNavigate('dashboard')}
          >
            Dashboard
          </Button>
          <Button
            variant="primary"
            icon={LogIn}
            onClick={handleSignIn}
          >
            Sign In Now
          </Button>
        </div>
      </div>
    </div>
  );
};

export default UnauthorizedView;
