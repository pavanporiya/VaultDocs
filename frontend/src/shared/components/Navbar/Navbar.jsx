import React from 'react';
import { Menu, Shield, Search, User } from 'lucide-react';
import Input from '../Input/Input';
import './Navbar.css';

/**
 * Reusable application Navbar component with logo branding, search placeholder,
 * mobile drawer toggle button, and account area placeholder.
 */
export const Navbar = ({
  onToggleSidebar,
  userPlaceholder = { name: 'Demo User', role: 'Developer' },
  searchQuery = '',
  onSearchChange,
  className = '',
}) => {
  return (
    <header className={`vd-navbar ${className}`}>
      <div className="vd-navbar__left">
        <button
          type="button"
          className="vd-navbar__menu-btn"
          onClick={onToggleSidebar}
          aria-label="Toggle navigation menu"
        >
          <Menu size={22} />
        </button>

        <a href="/" className="vd-navbar__brand">
          <div className="vd-navbar__logo">
            <Shield size={22} />
          </div>
          <span className="vd-navbar__brand-name">VaultDocs</span>
          <span className="vd-navbar__badge">v1.0</span>
        </a>
      </div>

      <div className="vd-navbar__center">
        <div className="vd-navbar__search">
          <Input
            type="search"
            placeholder="Search documents, folders, tags..."
            value={searchQuery}
            onChange={onSearchChange}
            icon={Search}
          />
        </div>
      </div>

      <div className="vd-navbar__right">
        <div className="vd-navbar__account-placeholder" title="Account placeholder">
          <div className="vd-navbar__avatar">
            <User size={18} />
          </div>
          <div className="vd-navbar__user-info">
            <span className="vd-navbar__user-name">{userPlaceholder.name}</span>
            <span className="vd-navbar__user-role">{userPlaceholder.role}</span>
          </div>
        </div>
      </div>
    </header>
  );
};

export default Navbar;
