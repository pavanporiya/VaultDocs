import React from 'react';
import { Menu, Shield, Search, User, LogOut, LogIn } from 'lucide-react';
import Input from '../Input/Input';
import Button from '../Button/Button';
import './Navbar.css';

/**
 * Reusable application Navbar component with logo branding, search placeholder,
 * mobile drawer toggle button, and authenticated user account area.
 */
export const Navbar = ({
  onToggleSidebar,
  user = null,
  onOpenAuthModal,
  onLogout,
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

        <a href="/" className="vd-navbar__brand" onClick={(e) => e.preventDefault()}>
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
            placeholder="Search documents by name..."
            value={searchQuery}
            onChange={onSearchChange}
            icon={Search}
          />
        </div>
      </div>

      <div className="vd-navbar__right">
        {user ? (
          <div className="vd-navbar__account-placeholder" title={user.email}>
            <div className="vd-navbar__avatar">
              <User size={18} />
            </div>
            <div className="vd-navbar__user-info">
              <span className="vd-navbar__user-name">{user.full_name || 'User'}</span>
              <span className="vd-navbar__user-role">{user.email}</span>
            </div>
            {onLogout && (
              <Button
                variant="ghost"
                size="sm"
                icon={LogOut}
                title="Log Out"
                onClick={onLogout}
                style={{ marginLeft: '0.5rem' }}
              />
            )}
          </div>
        ) : (
          <div className="vd-navbar__guest-actions">
            <Button
              variant="primary"
              size="sm"
              icon={LogIn}
              onClick={() => onOpenAuthModal && onOpenAuthModal('login')}
            >
              Sign In
            </Button>
          </div>
        )}
      </div>
    </header>
  );
};

export default Navbar;
