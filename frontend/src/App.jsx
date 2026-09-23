import React, { useState, useEffect, useCallback } from 'react';
import { AuthProvider, useAuth } from './shared/context/AuthContext';
import MainLayout from './shared/layouts/MainLayout';
import AuthModal from './features/auth/AuthModal';
import LoginView from './features/auth/LoginView';
import RegisterView from './features/auth/RegisterView';
import DashboardView from './features/dashboard/DashboardView';
import ExplorerView from './features/explorer/ExplorerView';
import DocumentsView from './features/documents/DocumentsView';
import SharedView from './features/shared_docs/SharedView';
import ProfileView from './features/account/ProfileView';
import SettingsView from './features/account/SettingsView';
import NotFoundView from './features/system/NotFoundView';
import UnauthorizedView from './features/system/UnauthorizedView';
import ForbiddenView from './features/system/ForbiddenView';
import ServerErrorView from './features/system/ServerErrorView';
import OfflineView from './features/system/OfflineView';
import SystemShowcaseView from './features/system/SystemShowcaseView';
import ShowcaseView from './features/showcase/ShowcaseView';
import './App.css';

const PATH_MAP = {
  '/': 'dashboard',
  '/dashboard': 'dashboard',
  '/explorer': 'folders',
  '/folders': 'folders',
  '/documents': 'documents',
  '/shared': 'sharing',
  '/sharing': 'sharing',
  '/login': 'login',
  '/register': 'register',
  '/profile': 'profile',
  '/settings': 'settings',
  '/404': '404',
  '/401': '401',
  '/403': '403',
  '/500': '500',
  '/offline': 'offline',
  '/system': 'system',
  '/showcase': 'showcase',
};

const ROUTE_PATH_MAP = {
  dashboard: '/dashboard',
  folders: '/explorer',
  documents: '/documents',
  sharing: '/shared',
  login: '/login',
  register: '/register',
  profile: '/profile',
  settings: '/settings',
  '404': '/404',
  '401': '/401',
  '403': '/403',
  '500': '/500',
  offline: '/offline',
  system: '/system',
  showcase: '/showcase',
};

const getNavFromPath = (path) => {
  const normalized = path.toLowerCase().replace(/\/$/, '') || '/';
  if (PATH_MAP[normalized]) {
    return PATH_MAP[normalized];
  }
  return '404';
};

function MainAppContent() {
  const { user, logout } = useAuth();
  const [activeNav, setActiveNavState] = useState(() => getNavFromPath(window.location.pathname));
  const [searchQuery, setSearchQuery] = useState('');

  // Auth modal state
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [authModalMode, setAuthModalMode] = useState('login');

  const handleNavigate = useCallback((navId) => {
    setActiveNavState(navId);
    const targetPath = ROUTE_PATH_MAP[navId] || `/${navId}`;
    if (window.location.pathname !== targetPath) {
      window.history.pushState({}, '', targetPath);
    }
  }, []);

  useEffect(() => {
    const handlePopState = () => {
      const navId = getNavFromPath(window.location.pathname);
      setActiveNavState(navId);
    };

    window.addEventListener('popstate', handlePopState);
    return () => window.removeEventListener('popstate', handlePopState);
  }, []);

  const handleOpenAuthModal = (mode = 'login') => {
    setAuthModalMode(mode);
    setIsAuthModalOpen(true);
  };

  const handleSearchChange = (e) => {
    const query = e.target.value;
    setSearchQuery(query);
    if (query.trim() && activeNav !== 'documents') {
      handleNavigate('documents');
    }
  };

  const renderActiveView = () => {
    switch (activeNav) {
      case 'dashboard':
        return (
          <DashboardView
            onNavigate={handleNavigate}
            onOpenAuthModal={handleOpenAuthModal}
          />
        );
      case 'folders':
        return <ExplorerView onOpenAuthModal={handleOpenAuthModal} />;
      case 'documents':
        return (
          <DocumentsView
            onOpenAuthModal={handleOpenAuthModal}
            searchQuery={searchQuery}
          />
        );
      case 'sharing':
        return <SharedView onOpenAuthModal={handleOpenAuthModal} />;
      case 'login':
        return <LoginView onNavigate={handleNavigate} />;
      case 'register':
        return <RegisterView onNavigate={handleNavigate} />;
      case 'profile':
        return <ProfileView onNavigate={handleNavigate} />;
      case 'settings':
        return <SettingsView onNavigate={handleNavigate} />;
      case '404':
        return <NotFoundView onNavigate={handleNavigate} />;
      case '401':
        return (
          <UnauthorizedView
            onNavigate={handleNavigate}
            onOpenAuthModal={handleOpenAuthModal}
          />
        );
      case '403':
        return <ForbiddenView onNavigate={handleNavigate} />;
      case '500':
        return <ServerErrorView onNavigate={handleNavigate} />;
      case 'offline':
        return <OfflineView onNavigate={handleNavigate} />;
      case 'system':
        return (
          <SystemShowcaseView
            onNavigate={handleNavigate}
            onOpenAuthModal={handleOpenAuthModal}
          />
        );
      case 'showcase':
        return <ShowcaseView />;
      default:
        return <NotFoundView onNavigate={handleNavigate} />;
    }
  };

  return (
    <>
      <MainLayout
        activeNavItem={activeNav}
        onNavItemClick={(item) => handleNavigate(item.id)}
        user={user}
        onOpenAuthModal={handleOpenAuthModal}
        onLogout={logout}
        onNavigate={handleNavigate}
        searchQuery={searchQuery}
        onSearchChange={handleSearchChange}
      >
        {renderActiveView()}
      </MainLayout>

      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        initialMode={authModalMode}
      />
    </>
  );
}

export function App() {
  return (
    <AuthProvider>
      <MainAppContent />
    </AuthProvider>
  );
}

export default App;
