import React, { useState } from 'react';
import { AuthProvider, useAuth } from './shared/context/AuthContext';
import MainLayout from './shared/layouts/MainLayout';
import AuthModal from './features/auth/AuthModal';
import DashboardView from './features/dashboard/DashboardView';
import ExplorerView from './features/explorer/ExplorerView';
import DocumentsView from './features/documents/DocumentsView';
import SharedView from './features/shared_docs/SharedView';
import ShowcaseView from './features/showcase/ShowcaseView';
import './App.css';

function MainAppContent() {
  const { user, logout } = useAuth();
  const [activeNav, setActiveNav] = useState('dashboard');
  const [searchQuery, setSearchQuery] = useState('');

  // Auth modal state
  const [isAuthModalOpen, setIsAuthModalOpen] = useState(false);
  const [authModalMode, setAuthModalMode] = useState('login');

  const handleOpenAuthModal = (mode = 'login') => {
    setAuthModalMode(mode);
    setIsAuthModalOpen(true);
  };

  const handleSearchChange = (e) => {
    const query = e.target.value;
    setSearchQuery(query);
    if (query.trim() && activeNav !== 'documents') {
      setActiveNav('documents');
    }
  };

  const renderActiveView = () => {
    switch (activeNav) {
      case 'dashboard':
        return (
          <DashboardView
            onNavigate={(navId) => setActiveNav(navId)}
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
      case 'showcase':
        return <ShowcaseView />;
      default:
        return (
          <DashboardView
            onNavigate={(navId) => setActiveNav(navId)}
            onOpenAuthModal={handleOpenAuthModal}
          />
        );
    }
  };

  return (
    <>
      <MainLayout
        activeNavItem={activeNav}
        onNavItemClick={(item) => setActiveNav(item.id)}
        user={user}
        onOpenAuthModal={handleOpenAuthModal}
        onLogout={logout}
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
