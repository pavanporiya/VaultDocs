import React from 'react';
import { FolderOpen } from 'lucide-react';
import './EmptyState.css';

/**
 * Reusable EmptyState component for empty document lists, search results, or tables.
 */
export const EmptyState = ({
  title = 'No records found',
  description = 'There are no items to display right now.',
  icon: Icon = FolderOpen,
  action,
  className = '',
}) => {
  return (
    <div className={`vd-empty-state ${className}`}>
      {Icon && (
        <div className="vd-empty-state__icon-wrapper">
          <Icon size={36} className="vd-empty-state__icon" />
        </div>
      )}
      <h4 className="vd-empty-state__title">{title}</h4>
      {description && <p className="vd-empty-state__description">{description}</p>}
      {action && <div className="vd-empty-state__action">{action}</div>}
    </div>
  );
};

export default EmptyState;
