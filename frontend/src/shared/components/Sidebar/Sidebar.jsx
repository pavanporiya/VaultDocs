import React from 'react';
import {
  LayoutDashboard,
  FolderOpen,
  FileText,
  Share2,
  User,
  Settings,
  SlidersHorizontal,
  X,
} from 'lucide-react';
import './Sidebar.css';

/**
 * Default sidebar navigation configuration matching the team feature architecture.
 */
export const DEFAULT_SIDEBAR_ITEMS = [
  { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard, path: '/dashboard' },
  { id: 'folders', label: 'Explorer / Folders', icon: FolderOpen, path: '/explorer' },
  { id: 'documents', label: 'All Documents', icon: FileText, path: '/documents' },
  { id: 'sharing', label: 'Shared With Me', icon: Share2, path: '/shared' },
  { id: 'profile', label: 'My Profile', icon: User, path: '/profile' },
  { id: 'settings', label: 'Settings', icon: Settings, path: '/settings' },
  { id: 'showcase', label: 'UI Showcase', icon: SlidersHorizontal, path: '/showcase' },
];

/**
 * Reusable application Sidebar component with active link indicators,
 * responsive mobile drawer overlay, and reusable configuration support.
 */
export const Sidebar = ({
  items = DEFAULT_SIDEBAR_ITEMS,
  activeItem = 'dashboard',
  onItemClick,
  isOpen = false,
  onCloseMobile,
  className = '',
}) => {
  return (
    <>
      {/* Mobile Backdrop Overlay */}
      {isOpen && (
        <div
          className="vd-sidebar-overlay"
          onClick={onCloseMobile}
          aria-hidden="true"
        />
      )}

      <aside
        className={`vd-sidebar ${isOpen ? 'vd-sidebar--open' : ''} ${className}`}
        aria-label="Main navigation"
      >
        <div className="vd-sidebar__header">
          <span className="vd-sidebar__header-title">Navigation</span>
          <button
            type="button"
            className="vd-sidebar__close-btn"
            onClick={onCloseMobile}
            aria-label="Close sidebar navigation"
          >
            <X size={20} />
          </button>
        </div>

        <nav className="vd-sidebar__nav">
          <ul className="vd-sidebar__list">
            {items.map((item) => {
              const Icon = item.icon;
              const isActive = activeItem === item.id;

              return (
                <li key={item.id} className="vd-sidebar__item">
                  <button
                    type="button"
                    className={`vd-sidebar__link ${isActive ? 'vd-sidebar__link--active' : ''}`}
                    onClick={() => onItemClick && onItemClick(item)}
                    aria-current={isActive ? 'page' : undefined}
                  >
                    {Icon && (
                      <span className="vd-sidebar__icon" aria-hidden="true">
                        <Icon size={20} />
                      </span>
                    )}
                    <span className="vd-sidebar__label">{item.label}</span>
                    {item.badge && (
                      <span className="vd-sidebar__badge">{item.badge}</span>
                    )}
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>

        <div className="vd-sidebar__footer">
          <div className="vd-sidebar__storage-info">
            <span className="vd-sidebar__storage-label">System Architecture</span>
            <span className="vd-sidebar__storage-status">Modular Monolith</span>
          </div>
        </div>
      </aside>
    </>
  );
};

export default Sidebar;
