import React from 'react';
import './Button.css';

/**
 * Reusable Button component with multiple variants, states, and accessibility support.
 */
export const Button = ({
  children,
  variant = 'primary', // 'primary' | 'secondary' | 'outline' | 'ghost' | 'danger'
  size = 'md', // 'sm' | 'md' | 'lg'
  type = 'button',
  onClick,
  disabled = false,
  loading = false,
  fullWidth = false,
  icon: Icon,
  iconPosition = 'left',
  className = '',
  'aria-label': ariaLabel,
  ...props
}) => {
  const isButtonDisabled = disabled || loading;

  return (
    <button
      type={type}
      className={`vd-button vd-button--${variant} vd-button--${size} ${
        fullWidth ? 'vd-button--full-width' : ''
      } ${loading ? 'vd-button--loading' : ''} ${className}`}
      onClick={onClick}
      disabled={isButtonDisabled}
      aria-disabled={isButtonDisabled}
      aria-busy={loading}
      aria-label={ariaLabel}
      {...props}
    >
      {loading && (
        <span className="vd-button__spinner" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
            <circle
              cx="12"
              cy="12"
              r="10"
              strokeWidth="4"
              strokeDasharray="31.4"
              strokeDashoffset="10"
            />
          </svg>
        </span>
      )}

      {!loading && Icon && iconPosition === 'left' && (
        <span className="vd-button__icon vd-button__icon--left" aria-hidden="true">
          <Icon size={size === 'sm' ? 16 : size === 'lg' ? 22 : 18} />
        </span>
      )}

      <span className="vd-button__content">{children}</span>

      {!loading && Icon && iconPosition === 'right' && (
        <span className="vd-button__icon vd-button__icon--right" aria-hidden="true">
          <Icon size={size === 'sm' ? 16 : size === 'lg' ? 22 : 18} />
        </span>
      )}
    </button>
  );
};

export default Button;
