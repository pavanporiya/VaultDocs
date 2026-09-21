import React, { useId } from 'react';
import './Input.css';

/**
 * Reusable form Input component supporting labels, helper text, error state, and accessibility.
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
          type={type}
          value={value}
          onChange={onChange}
          placeholder={placeholder}
          disabled={disabled}
          required={required}
          className={`vd-input ${Icon ? 'vd-input--has-icon' : ''}`}
          aria-invalid={!!error}
          aria-describedby={error ? errorId : helperText ? helperId : undefined}
          {...props}
        />
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
