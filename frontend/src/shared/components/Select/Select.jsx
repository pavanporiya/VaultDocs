import React, { useId } from 'react';
import './Select.css';

/**
 * Reusable Select dropdown component.
 */
export const Select = ({
  label,
  options = [],
  value,
  onChange,
  disabled = false,
  required = false,
  error,
  helperText,
  name,
  id,
  placeholder = 'Select an option...',
  className = '',
  ...props
}) => {
  const generatedId = useId();
  const selectId = id || `select-${generatedId}`;
  const errorId = `${selectId}-error`;
  const helperId = `${selectId}-helper`;

  return (
    <div className={`vd-select-group ${error ? 'vd-select-group--error' : ''} ${className}`}>
      {label && (
        <label htmlFor={selectId} className="vd-select-group__label">
          {label}
          {required && <span className="vd-select-group__required" aria-hidden="true">*</span>}
        </label>
      )}

      <div className="vd-select-wrapper">
        <select
          id={selectId}
          name={name}
          value={value}
          onChange={onChange}
          disabled={disabled}
          required={required}
          className="vd-select"
          aria-invalid={!!error}
          aria-describedby={error ? errorId : helperText ? helperId : undefined}
          {...props}
        >
          {placeholder && (
            <option value="" disabled hidden>
              {placeholder}
            </option>
          )}
          {options.map((opt) => (
            <option key={opt.value} value={opt.value} disabled={opt.disabled}>
              {opt.label}
            </option>
          ))}
        </select>
        <span className="vd-select-wrapper__arrow" aria-hidden="true">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M6 9l6 6 6-6" />
          </svg>
        </span>
      </div>

      {error && (
        <span id={errorId} className="vd-select-group__error" role="alert">
          {error}
        </span>
      )}

      {!error && helperText && (
        <span id={helperId} className="vd-select-group__helper">
          {helperText}
        </span>
      )}
    </div>
  );
};

export default Select;
