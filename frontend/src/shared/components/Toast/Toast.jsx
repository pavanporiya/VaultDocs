import React from 'react';
import { CheckCircle2, AlertCircle, AlertTriangle, Info, X } from 'lucide-react';
import './Toast.css';

const ICON_MAP = {
  success: CheckCircle2,
  error: AlertCircle,
  warning: AlertTriangle,
  info: Info,
};

/**
 * Individual Toast Notification Item component.
 */
export const ToastItem = ({ id, type = 'info', title, message, onClose }) => {
  const Icon = ICON_MAP[type] || Info;

  return (
    <div className={`vd-toast vd-toast--${type}`} role="status">
      <div className="vd-toast__icon" aria-hidden="true">
        <Icon size={20} />
      </div>

      <div className="vd-toast__content">
        {title && <div className="vd-toast__title">{title}</div>}
        {message && <div className="vd-toast__message">{message}</div>}
      </div>

      <button
        type="button"
        className="vd-toast__close"
        onClick={() => onClose(id)}
        aria-label="Close notification"
      >
        <X size={16} />
      </button>
    </div>
  );
};
