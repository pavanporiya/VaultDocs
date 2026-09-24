import React, { useState, useEffect, useCallback } from 'react';
import { AuthProvider, useAuth } from './shared/context/AuthContext';
import MainLayout from './shared/layouts/MainLayout';
import AuthModal from './features/auth/AuthModal';
import LoginView from './features/auth/LoginView';
import RegisterView from './features/auth/RegisterView';
import DashboardView from './features/dashboard/DashboardView';
import ExplorerView from './features/explorer/ExplorerView';
import DocumentsView from './features/documents/DocumentsView';
import DocumentDetailView from './features/documents/DocumentDetailView';
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

/**
 * Exact-match route table. Dynamic segments are supported with a `:param`
 * syntax; matched params are forwarded to the view as `routeParams`.
 */
const ROUTES = [
  { path: '/', view: 'dashboard' },
  { path: '/dashboard', view: 'dashboard' },
  { path: '/explorer', view: 'folders' },
  { path: '/folders', view: 'folders' },
  { path: '/documents', view: 'documents' },
  { path: '/documents/:documentId', view: 'documentDetail' },
  { path: '/shared', view: 'sharing' },
  { path: '/sharing', view: 'sharing' },
  { path: '/login', view: 'login' },
  { path: '/register', view: 'register' },
  { path: '/profile', view: 'profile' },
  { path: '/settings', view: 'settings' },
  { path: '/404', view: '404' },
  { path: '/401', view: '401' },
  { path: '/403', view: '403' },
  { path: '/500', view: '500' },
  { path: '/offline', view: 'offline' },
  { path: '/system', view: 'system' },
  { path: '/showcase', view: 'showcase' },
];

/**
 * Sidebar/nav ids mapped back to their canonical paths so nav-driven
 * navigation keeps working unchanged.
 */
const NAV_PATH_MAP = {
  dashboard: '/dashboard',
  folders: '/explorer',
  documents: '/documents',
  documentDetail: '/documents',
  sharing: '/shared',
  login: '/login',
  register: '/register',
  profile: '/profile',
  settings: '/settings',
  404: '/404',
  401: '/401',
  403: '/403',
  500: '/500',
  offline: '/offline',
  system: '/system',
  showcase: '/showcase',
};

/**
 * Resolve a window pathname against the route table.
 * Returns `{ view, params }` or `{ view: '404', params: {} }` for unknown paths.
 */
export const resolveRoute = (pathname) => {
  const normalized = (pathname || '/').split('?')[0].replace(/\/+$/, '') || '/';
  const pathSegments = normalized.split('/').filter(Boolean);

  for (const route of ROUTES) {
    const routeSegments = route.path.split('/').filter(Boolean);

    if (routeSegments.length !== pathSegments.length) continue;

    let matched = true;
    const params = {};
    for (let i = 0; i < routeSegments.length; i += 1) {
      const routeSeg = routeSegments[i];
      if (routeSeg.startsWith(':')) {
        if (!pathSegments[i]) {
          matched = false;
          break;
        }
        params[routeSeg.slice(1)] = decodeURIComponent(pathSegments[i]);
      } else if (routeSeg.toLowerCase() !== pathSegments[i].toLowerCase()) {
        matched = false;
        break;
      }
    }

    if (matched) {
      return { view: route.view, params };
    }
  }

  return { view: '404', params: {} };
};

/** Normalize a nav id or path into a canonical pushState target. */
const toPath = (target) => {
  if (typeof target === 'string' && target.startsWith('/')) {
    return target;
  }
  return NAV_PATH_MAP[target] || '/';
};

// Views reachable without authentication; everything else redirects to /401.
const PUBLIC_VIEWS = new Set([
  'login',
  'register',
  '401',
  '403',
  '404',
  '500',
  'offline',
  'system',
  'showcase',
  'dashboard',
]);

function MainAppContent() {
  const { user, logout, isAuthenticated } = useAuth();
  const [currentPath, setCurrentPath] = useState(
    () => window.location.pathname || '/'
  );
  const [searchQuery, setSearchQuery] = useState('');

  // Auth modal state
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [authModalMode, setAuthModalMode] = useState('login');

  const handleNavigate = useCallback((target) => {
    const targetPath = toPath(target);
    if (window.location.pathname !== targetPath) {
      window.history.pushState({}, '', targetPath);
    }
    setCurrentPath(window.location.pathname);
  }, []);

  useEffect(() => {
    const handlePopState = () => {
      setCurrentPath(window.location.pathname);
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
    if (
      query.trim() &&
      window.location.pathname !== '/documents'
    ) {
      // Typing a search from anywhere (incl. a document detail page) goes to
      // the documents list, where live backend search results are shown.
      handleNavigate('/documents');
    }
  };

  const route = resolveRoute(currentPath);
  const { view, params } = route;

  // Protected views: an unauthenticated visitor is routed to /401.
  const isProtectedView = !PUBLIC_VIEWS.has(view);
  const showUnauthorized = isProtectedView && !isAuthenticated;

  const renderActiveView = () => {
    if (showUnauthorized) {
      return (
        <UnauthorizedView
          onNavigate={handleNavigate}
          onOpenAuthModal={handleOpenAuthModal}
        />
      );
    }

    switch (view) {
      case 'dashboard':
        return (
          <DashboardView
            onNavigate={handleNavigate}
            onOpenAuthModal={handleOpenAuthModal}
          />
        );
      case 'folders':
        return (
          <ExplorerView
            onOpenAuthModal={handleOpenAuthModal}
            onNavigate={handleNavigate}
          />
        );
      case 'documents':
        return (
          <DocumentsView
            onOpenAuthModal={handleOpenAuthModal}
            onNavigate={handleNavigate}
            searchQuery={searchQuery}
          />
        );
      case 'documentDetail':
        return (
          <DocumentDetailView
            documentId={params.documentId}
            onNavigate={handleNavigate}
          />
        );
      case 'sharing':
        return <SharedView onOpenAuthModal={handleOpenAuthModal} onNavigate={handleNavigate} />;
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
    <MainLayout
      activeNavItem={view}
      onNavItemClick={(item) => handleNavigate(item.id || item.path)}
      user={user}
      onOpenAuthModal={handleOpenAuthModal}
      onLogout={logout}
      onNavigate={handleNavigate}
      searchQuery={searchQuery}
      onSearchChange={handleSearchChange}
    >
      {renderActiveView()}

      <AuthModal
        isOpen={isAuthModalOpen}
        onClose={() => setIsAuthModalOpen(false)}
        initialMode={authModalMode}
      />
    </MainLayout>
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
