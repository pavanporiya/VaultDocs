import React, { useId, useState } from 'react';
import { Eye, EyeOff } from 'lucide-react';
import './Input.css';

/**
 * Reusable form Input component supporting labels, helper text, error state,
 * password visibility toggling, and accessibility.
 */
export const Input = ({
  label,
  type = 'text',
  placeholder,
  value,
  onChange,
  disabled = false,
  required = false,
  error,
  helperText,
  icon: Icon,
  name,
  id,
  className = '',
  ...props
}) => {
  const generatedId = useId();
  const inputId = id || `input-${generatedId}`;
  const errorId = `${inputId}-error`;
  const helperId = `${inputId}-helper`;
  const [showPassword, setShowPassword] = useState(false);

  const isPassword = type === 'password';
  const resolvedType = isPassword ? (showPassword ? 'text' : 'password') : type;

  return (
    <div className={`vd-input-group ${error ? 'vd-input-group--error' : ''} ${className}`}>
      {label && (
        <label htmlFor={inputId} className="vd-input-group__label">
          {label}
          {required && <span className="vd-input-group__required" aria-hidden="true">*</span>}
        </label>
      )}

      <div className="vd-input-wrapper">
        {Icon && (
          <span className="vd-input-wrapper__icon" aria-hidden="true">
            <Icon size={18} />
          </span>
        )}
        <input
          id={inputId}
          name={name}
          type={resolvedType}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          disabled={disabled}
          required={required}
          className={`vd-input ${Icon ? 'vd-input--has-icon' : ''} ${isPassword ? 'vd-input--has-toggle' : ''}`}
          aria-invalid={!!error}
          aria-describedby={error ? errorId : helperText ? helperId : undefined}
          {...props}
        />
        {isPassword && (
          <button
            type="button"
            className="vd-input-password-toggle"
            onClick={() => setShowPassword((prev) => !prev)}
            disabled={disabled}
            aria-label={showPassword ? 'Hide password' : 'Show password'}
            title={showPassword ? 'Hide password' : 'Show password'}
            aria-pressed={showPassword}
            tabIndex={0}
          >
            {showPassword ? (
              <EyeOff size={18} aria-hidden="true" />
            ) : (
              <Eye size={18} aria-hidden="true" />
            )}
          </button>
        )}
      </div>

      {error && (
        <span id={errorId} className="vd-input-group__error" role="alert">
          {error}
        </span>
      )}

      {!error && helperText && (
        <span id={helperId} className="vd-input-group__helper">
          {helperText}
        </span>
      )}
    </div>
  );
};

export default Input;
