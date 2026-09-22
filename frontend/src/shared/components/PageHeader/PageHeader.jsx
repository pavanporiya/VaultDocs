import React from 'react';
import { ChevronRight } from 'lucide-react';
import './PageHeader.css';

/**
 * Reusable PageHeader component supporting titles, descriptions, breadcrumbs, and actions.
 */
export const PageHeader = ({
  title,
  description,
  breadcrumbs = [],
  actions,
  className = '',
}) => {
  return (
    <div className={`vd-page-header ${className}`}>
      {breadcrumbs.length > 0 && (
        <nav aria-label="Breadcrumb" className="vd-page-header__breadcrumbs">
          <ol className="vd-breadcrumb__list">
            {breadcrumbs.map((crumb, idx) => {
              const isLast = idx === breadcrumbs.length - 1;
              return (
                <li key={idx} className="vd-breadcrumb__item">
                  {isLast ? (
                    <span className="vd-breadcrumb__current" aria-current="page">
                      {crumb.label}
                    </span>
                  ) : (
                    <>
                      {crumb.onClick ? (
                        <button
                          type="button"
                          onClick={crumb.onClick}
                          className="vd-breadcrumb__link"
                        >
                          {crumb.label}
                        </button>
                      ) : crumb.href ? (
                        <a href={crumb.href} className="vd-breadcrumb__link">
                          {crumb.label}
                        </a>
                      ) : (
                        <span className="vd-breadcrumb__text">{crumb.label}</span>
                      )}
                      <ChevronRight size={14} className="vd-breadcrumb__separator" />
                    </>
                  )}
                </li>
              );
            })}
          </ol>
        </nav>
      )}

      <div className="vd-page-header__main">
        <div className="vd-page-header__titles">
          <h1 className="vd-page-header__title">{title}</h1>
          {description && <p className="vd-page-header__description">{description}</p>}
        </div>

        {actions && <div className="vd-page-header__actions">{actions}</div>}
      </div>
    </div>
  );
};

export default PageHeader;
