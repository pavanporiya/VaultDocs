import React, { useEffect, useId } from 'react';
import { X } from 'lucide-react';
import './Modal.css';

/**
 * Reusable accessible Modal dialog component with backdrop click, Escape key handling,
 * and body scroll locking.
 */
export const Modal = ({
  isOpen,
  onClose,
  title,
  children,
  footer,
  size = 'md', // 'sm' | 'md' | 'lg' | 'xl'
  closeOnOverlayClick = true,
  className = '',
}) => {
  const generatedId = useId();
  const titleId = `modal-title-${generatedId}`;

  // Escape Key Handler & Body Scroll Lock
  useEffect(() => {
    if (!isOpen) return;

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    document.body.style.overflow = 'hidden';

    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.body.style.overflow = '';
    };
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="vd-modal-overlay" onClick={closeOnOverlayClick ? onClose : undefined}>
      <div
        className={`vd-modal vd-modal--${size} ${className}`}
        role="dialog"
        aria-modal="true"
        aria-labelledby={title ? titleId : undefined}
        onClick={(e) => e.stopPropagation()} // Prevent overlay close when clicking modal content
      >
        <div className="vd-modal__header">
          {title && (
            <h2 id={titleId} className="vd-modal__title">
              {title}
            </h2>
          )}
          <button
            type="button"
            className="vd-modal__close"
            onClick={onClose}
            aria-label="Close dialog"
          >
            <X size={20} />
          </button>
        </div>

        <div className="vd-modal__body">{children}</div>

        {footer && <div className="vd-modal__footer">{footer}</div>}
      </div>
    </div>
  );
};

export default Modal;
