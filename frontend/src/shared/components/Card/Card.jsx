import React from 'react';
import './Card.css';

/**
 * Reusable Card component supporting headers, subtitles, main content, and footers.
 */
export const Card = ({
  title,
  subtitle,
  headerAction,
  children,
  footer,
  className = '',
  bodyClassName = '',
  elevation = 'sm', // 'flat' | 'sm' | 'md' | 'lg'
  padding = 'md', // 'none' | 'sm' | 'md' | 'lg'
  ...props
}) => {
  return (
    <div
      className={`vd-card vd-card--elevation-${elevation} vd-card--padding-${padding} ${className}`}
      {...props}
    >
      {(title || subtitle || headerAction) && (
        <div className="vd-card__header">
          <div className="vd-card__header-titles">
            {title && <h3 className="vd-card__title">{title}</h3>}
            {subtitle && <p className="vd-card__subtitle">{subtitle}</p>}
          </div>
          {headerAction && <div className="vd-card__header-action">{headerAction}</div>}
        </div>
      )}

      <div className={`vd-card__body ${bodyClassName}`}>{children}</div>

      {footer && <div className="vd-card__footer">{footer}</div>}
    </div>
  );
};

export default Card;
