import React, { useState } from 'react';
import { PageHeader, Card, Button, EmptyState, Loader } from '../../shared/components';
import NotFoundView from './NotFoundView';
import UnauthorizedView from './UnauthorizedView';
import ForbiddenView from './ForbiddenView';
import ServerErrorView from './ServerErrorView';
import OfflineView from './OfflineView';
import { FolderOpen } from 'lucide-react';
import './System.css';

export const SystemShowcaseView = ({ onNavigate, onOpenAuthModal }) => {
  const [selectedState, setSelectedState] = useState('all');

  return (
    <div className="vd-account-view">
      <PageHeader
        title="System States & Utility Showcase"
        description="Comprehensive preview of 404, 401, 403, 500, Offline, Empty States, and Loading States reusing Common UI components."
        breadcrumbs={[
          { label: 'Dashboard', onClick: () => onNavigate && onNavigate('dashboard') },
          { label: 'System Showcase' },
        ]}
      />

      <Card title="Select System State View" elevation="sm">
        <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
          {['all', '404', '401', '403', '500', 'offline', 'empty', 'loading'].map((tab) => (
            <Button
              key={tab}
              variant={selectedState === tab ? 'primary' : 'outline'}
              size="sm"
              onClick={() => setSelectedState(tab)}
            >
              {tab.toUpperCase()} State
            </Button>
          ))}
        </div>
      </Card>

      {(selectedState === 'all' || selectedState === '404') && (
        <Card title="HTTP 404 - Not Found State" elevation="sm">
          <NotFoundView onNavigate={onNavigate} />
        </Card>
      )}

      {(selectedState === 'all' || selectedState === '401') && (
        <Card title="HTTP 401 - Unauthorized State" elevation="sm">
          <UnauthorizedView onNavigate={onNavigate} onOpenAuthModal={onOpenAuthModal} />
        </Card>
      )}

      {(selectedState === 'all' || selectedState === '403') && (
        <Card title="HTTP 403 - Forbidden State" elevation="sm">
          <ForbiddenView onNavigate={onNavigate} />
        </Card>
      )}

      {(selectedState === 'all' || selectedState === '500') && (
        <Card title="HTTP 500 - Internal Server Error State" elevation="sm">
          <ServerErrorView onNavigate={onNavigate} onRetry={() => alert('Retry triggered')} />
        </Card>
      )}

      {(selectedState === 'all' || selectedState === 'offline') && (
        <Card title="Network Offline State" elevation="sm">
          <OfflineView onNavigate={onNavigate} />
        </Card>
      )}

      {(selectedState === 'all' || selectedState === 'empty') && (
        <Card title="Empty State Reusability" elevation="sm">
          <EmptyState
            title="No Documents Found"
            description="There are no documents matching your query or filter criteria in this vault."
            icon={FolderOpen}
            action={
              <Button variant="primary" size="sm" onClick={() => onNavigate && onNavigate('documents')}>
                Browse All Documents
              </Button>
            }
          />
        </Card>
      )}

      {(selectedState === 'all' || selectedState === 'loading') && (
        <Card title="Loading States Reusability" elevation="sm">
          <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem', padding: '1rem 0' }}>
            <div>
              <h4 style={{ fontSize: '0.875rem', marginBottom: '0.5rem' }}>Component Level Loader:</h4>
              <Loader variant="component" size="md" text="Loading document details..." />
            </div>
            <div>
              <h4 style={{ fontSize: '0.875rem', marginBottom: '0.5rem' }}>Inline Loader:</h4>
              <Loader variant="inline" size="sm" text="Updating status..." />
            </div>
          </div>
        </Card>
      )}
    </div>
  );
};

export default SystemShowcaseView;
