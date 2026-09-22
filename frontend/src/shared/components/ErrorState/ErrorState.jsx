import React from 'react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import Button from '../Button/Button';
import './ErrorState.css';

/**
 * Reusable ErrorState component for displaying safe error boundaries and failed requests.
 * Ensures stack traces, raw backend exceptions, and database details are NEVER exposed.
 */
export const ErrorState = ({
  title = 'Something went wrong',
  description = 'An unexpected error occurred while loading this section. Please try again.',
  onRetry,
  retryLabel = 'Try Again',
  icon: Icon = AlertTriangle,
  className = '',
}) => {
  return (
    <div className={`vd-error-state ${className}`} role="alert">
      {Icon && (
        <div className="vd-error-state__icon-wrapper">
          <Icon size={36} className="vd-error-state__icon" />
        </div>
      )}
      <h4 className="vd-error-state__title">{title}</h4>
      <p className="vd-error-state__description">{description}</p>
      {onRetry && (
        <div className="vd-error-state__action">
          <Button variant="secondary" icon={RefreshCw} onClick={onRetry}>
            {retryLabel}
          </Button>
        </div>
      )}
    </div>
  );
};

export default ErrorState;
