import React from 'react';
import './Loader.css';

/**
 * Reusable Loader component supporting page overlay, component level, and inline spinners.
 */
export const Loader = ({
  variant = 'component', // 'page' | 'component' | 'inline'
  size = 'md', // 'sm' | 'md' | 'lg'
  text,
  className = '',
}) => {
  return (
    <div className={`vd-loader-container vd-loader-container--${variant} ${className}`}>
      <div className={`vd-spinner vd-spinner--${size}`} role="status" aria-live="polite">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
          <circle
            cx="12"
            cy="12"
            r="10"
            strokeWidth="3.5"
            strokeDasharray="31.4"
            strokeDashoffset="10"
          />
        </svg>
        <span className="visually-hidden">{text || 'Loading...'}</span>
      </div>
      {text && <span className="vd-loader__text">{text}</span>}
    </div>
  );
};

export default Loader;
