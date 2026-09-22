import React from 'react';
import EmptyState from '../EmptyState/EmptyState';
import './Table.css';

/**
 * Reusable accessible Table component supporting dynamic columns, loading skeletons,
 * empty state integration, and horizontal responsive scrolling.
 */
export const Table = ({
  columns = [],
  data = [],
  loading = false,
  emptyTitle = 'No data available',
  emptyDescription = 'There are no records to display at this time.',
  emptyAction,
  keyExtractor = (item, index) => item.id || index,
  className = '',
}) => {
  return (
    <div className={`vd-table-container ${className}`}>
      <div className="vd-table-scroll">
        <table className="vd-table">
          <thead>
            <tr>
              {columns.map((col) => (
                <th
                  key={col.key || col.header}
                  scope="col"
                  style={{
                    width: col.width || 'auto',
                    textAlign: col.align || 'left',
                  }}
                  className="vd-table__th"
                >
                  {col.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading ? (
              // Loading Skeleton Rows
              Array.from({ length: 4 }).map((_, idx) => (
                <tr key={`skeleton-${idx}`} className="vd-table__tr-skeleton">
                  {columns.map((col, cIdx) => (
                    <td key={`sk-cell-${cIdx}`} className="vd-table__td">
                      <div className="vd-table__skeleton-bar" />
                    </td>
                  ))}
                </tr>
              ))
            ) : data.length === 0 ? (
              // Empty State Row
              <tr>
                <td colSpan={columns.length} className="vd-table__td-empty">
                  <EmptyState
                    title={emptyTitle}
                    description={emptyDescription}
                    action={emptyAction}
                  />
                </td>
              </tr>
            ) : (
              // Data Rows
              data.map((row, rIdx) => (
                <tr key={keyExtractor(row, rIdx)} className="vd-table__tr">
                  {columns.map((col) => {
                    const value = row[col.key];
                    const content = col.render ? col.render(row, rIdx) : value;
                    return (
                      <td
                        key={col.key}
                        style={{ textAlign: col.align || 'left' }}
                        className="vd-table__td"
                      >
                        {content}
                      </td>
                    );
                  })}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};

export default Table;
