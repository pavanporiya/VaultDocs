import React, { useState } from 'react';
import Navbar from '../components/Navbar/Navbar';
import Sidebar, { DEFAULT_SIDEBAR_ITEMS } from '../components/Sidebar/Sidebar';
import ToastProvider from '../components/Toast/ToastContext';
import { useOnlineStatus } from '../hooks/useOnlineStatus';
import { WifiOff } from 'lucide-react';
import './MainLayout.css';

/**
 * Reusable MainLayout component wrapping the application's Navbar, Sidebar,
 * main content viewport, offline banner, and Toast notification container.
 */
export const MainLayout = ({
  children,
  sidebarItems = DEFAULT_SIDEBAR_ITEMS,
  activeNavItem = 'dashboard',
  onNavItemClick,
  user,
  onOpenAuthModal,
  onLogout,
  onNavigate,
  searchQuery,
  onSearchChange,
  className = '',
}) => {
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState(false);
  const isOnline = useOnlineStatus();

  const toggleMobileSidebar = () => {
    setIsMobileSidebarOpen((prev) => !prev);
  };

  const handleSidebarItemClick = (item) => {
    setIsMobileSidebarOpen(false);
    if (onNavItemClick) {
      onNavItemClick(item);
    }
  };

  return (
    <ToastProvider>
      <div className={`vd-main-layout ${className}`}>
        <Navbar
          onToggleSidebar={toggleMobileSidebar}
          user={user}
          onOpenAuthModal={onOpenAuthModal}
          onLogout={onLogout}
          onNavigate={onNavigate}
          searchQuery={searchQuery}
          onSearchChange={onSearchChange}
        />

        {!isOnline && (
          <div className="vd-offline-banner" role="status" aria-live="polite">
            <WifiOff size={16} />
            <span>
              You are offline — VaultDocs cannot reach the server. Actions will fail until the
              connection is restored.
            </span>
          </div>
        )}

        <div className="vd-main-layout__body">
          <Sidebar
            items={sidebarItems}
            activeItem={activeNavItem}
            onItemClick={handleSidebarItemClick}
            isOpen={isMobileSidebarOpen}
            onCloseMobile={() => setIsMobileSidebarOpen(false)}
          />

          <main className="vd-main-layout__content" id="main-content">
            <div className="vd-main-layout__container">{children}</div>
          </main>
        </div>
      </div>
    </ToastProvider>
  );
};

export default MainLayout;
